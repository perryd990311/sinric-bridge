# Migration Guide — v2 (Single-Service) → v3 (Multi-Service)

This guide covers upgrading from the original single-WiFi-SSID version to the
current multi-service architecture that uses `SERVICES_CONFIG`.

---

## Breaking Changes

| Area | What broke |
|---|---|
| `SINRIC_DEVICE_ID` env var | **Removed.** Service logs an error and ignores it. |
| `UNIFI_WLAN_ID` env var | **Removed.** Service logs an error and ignores it. |
| `/wifi/on`, `/wifi/off` endpoints | **Removed.** Replaced by `/service/{device_id}/on` etc. |
| `/wifi/details` endpoint | **Removed.** Replaced by `/service/{device_id}/details`. |
| Single-device operation | The service now requires at least one entry in `SERVICES_CONFIG` or nothing happens. |

---

## Old → New Environment Variable Mapping

| Old variable | New equivalent | Notes |
|---|---|---|
| `SINRIC_DEVICE_ID` | `device_id` field inside `SERVICES_CONFIG` entry | One entry per device |
| `UNIFI_WLAN_ID` | `config.wlan_id` field inside `SERVICES_CONFIG` entry | Per-service config |
| `UNIFI_HOST` | `UNIFI_HOST` | Unchanged — shared across all WiFi services |
| `UNIFI_API_KEY` | `UNIFI_API_KEY` | Unchanged |
| `UNIFI_SITE_ID` | `UNIFI_SITE_ID` | Unchanged |
| `SINRIC_APP_KEY` | `SINRIC_APP_KEY` | Unchanged |
| `SINRIC_APP_SECRET` | `SINRIC_APP_SECRET` | Unchanged |
| `API_TOKEN` | `API_TOKEN` | Unchanged |
| `ALLOWED_HOSTS` | `ALLOWED_HOSTS` | Unchanged |

---

## Before / After docker-compose

### Before (v2 — single service)

```yaml
environment:
  UNIFI_HOST: "192.168.1.1"
  UNIFI_API_KEY: "${UNIFI_API_KEY}"
  UNIFI_SITE_ID: "${UNIFI_SITE_ID}"
  SINRIC_APP_KEY: "${SINRIC_APP_KEY}"
  SINRIC_APP_SECRET: "${SINRIC_APP_SECRET}"
  SINRIC_DEVICE_ID: "abc-123-device-uuid"   # ← REMOVED
  UNIFI_WLAN_ID: "wlan-uuid-here"           # ← REMOVED
  API_TOKEN: "${API_TOKEN}"
```

### After (v3 — multi-service)

```yaml
environment:
  UNIFI_HOST: "192.168.1.1"
  UNIFI_API_KEY: "${UNIFI_API_KEY}"
  UNIFI_SITE_ID: "${UNIFI_SITE_ID}"
  SINRIC_APP_KEY: "${SINRIC_APP_KEY}"
  SINRIC_APP_SECRET: "${SINRIC_APP_SECRET}"
  API_TOKEN: "${API_TOKEN}"
  SERVICES_CONFIG: >-
    [
      {"device_id": "abc-123-device-uuid", "type": "wifi_ssid",
       "name": "Guest WiFi", "config": {"wlan_id": "wlan-uuid-here"}}
    ]
```

The old `device_id` and `wlan_id` values map directly into the JSON — no new
UUIDs needed; keep the same values you already registered with Sinric Pro.

---

## Old API Endpoints → New API Endpoints

| Old endpoint | New endpoint | Auth change |
|---|---|---|
| `POST /wifi/on` | `POST /service/{device_id}/on` | Same (IP + `X-API-Key`) |
| `POST /wifi/off` | `POST /service/{device_id}/off` | Same |
| `POST /wifi/toggle` | `POST /service/{device_id}/toggle` | Same |
| `GET /wifi/details` | `GET /service/{device_id}/details` | Same |
| `GET /health` | `GET /health` | Unchanged (no auth) |
| _(none)_ | `GET /services` | New — lists all registered services (IP only) |

Replace `{device_id}` with the value you previously had in `SINRIC_DEVICE_ID`.

**Example — old call:**
```bash
curl -X POST http://nas:8000/wifi/on -H "X-API-Key: $API_TOKEN"
```

**Example — new call:**
```bash
curl -X POST http://nas:8000/service/abc-123-device-uuid/on \
  -H "X-API-Key: $API_TOKEN"
```

---

## Backward Compatibility Notes

There is **no silent fallback**. If you start the service with the old env vars:

```
ERROR - Detected legacy env vars (SINRIC_DEVICE_ID=set, UNIFI_WLAN_ID=set).
        These are no longer supported.
        Migrate to SERVICES_CONFIG JSON array. See examples/services-config.json.
```

If `SERVICES_CONFIG` is also absent:

```
WARNING - No services configured — set SERVICES_CONFIG env var as a JSON array.
```

The service will start and the WebSocket will connect to Sinric Pro, but **no
actions will be routed** — Sinric commands will be silently ignored.

---

## Step-by-Step Migration Checklist

- [ ] Open your `docker-compose.yml` (or `.env` file)
- [ ] Note your current `SINRIC_DEVICE_ID` value (e.g., `abc-123-device-uuid`)
- [ ] Note your current `UNIFI_WLAN_ID` value (e.g., `wlan-uuid-here`)
- [ ] Add the `SERVICES_CONFIG` variable using the mapping above
- [ ] Remove `SINRIC_DEVICE_ID` and `UNIFI_WLAN_ID` from the compose file / env
- [ ] Rebuild and restart the container: `docker compose up -d --build`
- [ ] Check logs: `docker compose logs -f wifi-toggle` — confirm no ERROR lines about legacy vars
- [ ] Verify the service list: `curl http://nas:8000/services` (from your local network)
- [ ] Test a manual action: `curl -X POST http://nas:8000/service/{device_id}/on -H "X-API-Key: $API_TOKEN"`
- [ ] Test the Alexa voice command

---

## Troubleshooting

### Service starts but does nothing when I say the voice command

**Cause:** `SERVICES_CONFIG` is missing, empty, or has a JSON parse error.

**Check:** Look for this in logs:
```
WARNING - No services configured — set SERVICES_CONFIG env var as a JSON array.
```
or:
```
ERROR - SERVICES_CONFIG is not valid JSON: ...
```

**Fix:** Set `SERVICES_CONFIG` to a valid JSON array. Validate the JSON first:
```bash
echo "$SERVICES_CONFIG" | python -m json.tool
```

In docker-compose YAML, wrap with `>-` (block scalar) to safely embed JSON:
```yaml
SERVICES_CONFIG: >-
  [{"device_id": "my-device", "type": "wifi_ssid", "name": "My WiFi",
    "config": {"wlan_id": "my-wlan-uuid"}}]
```

---

### `/service/{device_id}/on` returns 404

**Cause:** The `device_id` in the URL doesn't match any entry in `SERVICES_CONFIG`, or
the handler failed `verify_configuration()` at startup and was skipped.

**Check logs for:**
```
WARNING - Handler 'my-device' failed verification — skipping
```
or:
```
ERROR - Device 'my-device' has no wlan_id in config
```

**Fix:** Confirm `device_id` matches exactly (case-sensitive), and that `config.wlan_id` is set.

---

### Sinric says device is unreachable

**Cause:** The `device_id` in `SERVICES_CONFIG` doesn't match the device UUID registered
in the Sinric Pro portal.

**Fix:** Log into [portal.sinric.pro](https://portal.sinric.pro), find your device, copy
its exact ID, and use that as `device_id` in `SERVICES_CONFIG`.

---

### `403 Access denied — local network only`

**Cause:** You're calling a local endpoint from an IP outside the `ALLOWED_HOSTS` ranges.

**Fix:** Either call from a LAN IP, or add your IP/CIDR to `ALLOWED_HOSTS`:
```yaml
ALLOWED_HOSTS: "127.0.0.1,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8,203.0.113.5/32"
```
