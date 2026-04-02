# Release Notes — home-automation Python service

---

## v3.0.0 — Multi-Service Architecture

**Released:** 2026-04-02

This release replaces the single-device WiFi SSID service with a fully
generalized multi-service architecture. A single container instance can now
manage any number of devices — across multiple service types — through one
Sinric Pro WebSocket connection and a unified REST API. The path to adding new
device types (garage doors, smart plugs, etc.) is now a single Python class.

---

### New Features

- **Multi-service support** — declare any number of devices via the
  `SERVICES_CONFIG` environment variable (JSON array); no code changes needed
  for new devices of an existing type.

  ```yaml
  SERVICES_CONFIG: >-
    [
      {"device_id": "abc-123", "type": "wifi_ssid",
       "name": "Guest WiFi", "config": {"wlan_id": "wlan-uuid-here"}},
      {"device_id": "def-456", "type": "wifi_ssid",
       "name": "IoT WiFi",   "config": {"wlan_id": "wlan-uuid-iot"}}
    ]
  ```

- **`ServiceHandler` abstract base class** — implement `handle_action()`,
  `get_state()`, `get_details()`, and `verify_configuration()` to add a new
  device type; see [docs/ADDING_NEW_SERVICES.md](docs/ADDING_NEW_SERVICES.md).

- **Generic Sinric Pro WebSocket routing** — one persistent connection handles
  all registered devices; commands are dispatched to the correct handler by
  `device_id`.

- **Parameterized REST API endpoints:**

  | Method | Path | Description |
  |--------|------|-------------|
  | `POST` | `/service/{device_id}/on` | Turn device on |
  | `POST` | `/service/{device_id}/off` | Turn device off |
  | `POST` | `/service/{device_id}/toggle` | Toggle device state |
  | `GET`  | `/service/{device_id}/details` | Device details |
  | `GET`  | `/services` | List all registered services |

- **`GET /services`** — returns all registered services and their current
  state; restricted to local-network access.

- **Startup verification** — each handler runs `verify_configuration()` at
  startup; misconfigured handlers are skipped with a warning rather than
  preventing the service from starting.

- **Legacy env var detection** — if `SINRIC_DEVICE_ID` or `UNIFI_WLAN_ID` are
  set, the service logs a clear error and exits rather than silently
  misconfiguring.

- **HTTP 502 on operation failure** — operations that fail downstream now
  return `502 Bad Gateway` instead of `200 OK` with `"success": false`.

- **Optimized Dockerfile layer caching** — `requirements.txt` is copied and
  installed before application code, so dependency layers are only rebuilt when
  dependencies actually change.

---

### Breaking Changes

> **Upgrading from v2? See the full migration guide:**
> [python-service/MIGRATION_GUIDE.md](python-service/MIGRATION_GUIDE.md)

- `SINRIC_DEVICE_ID` environment variable **removed**. The device ID is now
  the `device_id` field inside each `SERVICES_CONFIG` entry.

- `UNIFI_WLAN_ID` environment variable **removed**. The WLAN ID is now the
  `config.wlan_id` field inside each `SERVICES_CONFIG` entry.

- `/wifi/on`, `/wifi/off`, `/wifi/toggle`, `/wifi/details` endpoints
  **removed**. Replace with `/service/{device_id}/on` etc., using the same
  device UUID you registered with Sinric Pro.

---

### Migration

Full before/after environment variable mapping and docker-compose examples are
in [python-service/MIGRATION_GUIDE.md](python-service/MIGRATION_GUIDE.md).

---

### Bug Fixes (Internal)

These issues were identified and resolved during the v3 refactor:

- **Event loop blocking** — HTTP calls inside async handler methods now run via
  `asyncio.to_thread()`, preventing the FastAPI event loop from blocking under
  load.

- **Error detail leak** — API error responses previously echoed internal
  exception messages to callers. Responses now return a generic message; full
  detail is written to the server log only.

- **`/services` access control** — the endpoint now enforces local-network-only
  access (consistent with all other endpoints that require `ALLOWED_HOSTS`
  validation).

- **Sinric device registration** — the WebSocket handshake now registers only
  the device IDs whose handlers successfully passed `verify_configuration()`,
  not every entry in the raw config list.

- **Non-JSON WebSocket frames** — unexpected non-JSON frames from Sinric Pro
  now emit a warning log entry instead of an unhandled exception traceback.

- **Handler startup verification** — a handler that raises inside
  `verify_configuration()` is now skipped gracefully; the remaining handlers
  still start and the service remains available.

---

### Known Limitations

- **WebSocket reconnect delay** — the auto-reconnect loop uses a fixed 5-second
  delay. Exponential backoff is tracked for v3.1.

- **`core/` utilities not wired into `main.py`** — the `core/` package
  (`async_helpers`, `http`, `logging`, etc.) was extracted in this release but
  `main.py` does not yet import from it. Full adoption is planned for v3.1.

---

### Extending the Service

To add a new device type (garage door, smart plug, sensor, etc.) see
[docs/ADDING_NEW_SERVICES.md](docs/ADDING_NEW_SERVICES.md).

---

## v2.0.0 — Single WiFi SSID Service

Single-device WiFi SSID control via Sinric Pro. See git history for details.
