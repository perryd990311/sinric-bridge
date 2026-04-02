# python-service — Sinric Pro Multi-Service Bridge

A FastAPI + WebSocket service that connects Sinric Pro virtual devices to local
home-automation APIs (UniFi, custom HTTP, etc.). Voice commands from Alexa flow
through Sinric Pro's cloud, down a secure outbound WebSocket, and into this
service which calls whatever local API the device needs.

No port forwarding. No IFTTT. No public URL.

---

## Architecture

```
Alexa voice command
        │
        ▼
  Alexa Routine
        │
        ▼
  Sinric Pro cloud  ←──── portal.sinric.pro (register virtual devices here)
        │
        ▼  outbound WebSocket (HMAC-signed, TLS)
        │
  [this service — Docker container on Synology NAS]
        │
        ├── WiFiSSIDHandler  →  UniFi Gateway REST API
        ├── GarageDoorHandler → HTTP API on local controller
        └── (your handler)  →  any downstream API
```

---

## Quick Start

1. Copy the example compose file:
   ```bash
   cp examples/docker-compose-multiservice.yml ../docker/docker-compose.yml
   ```

2. Create a `.env` file next to `docker-compose.yml` with real secrets (never commit this):
   ```bash
   UNIFI_API_KEY=your-unifi-api-key
   UNIFI_SITE_ID=your-site-uuid
   SINRIC_APP_KEY=your-sinric-app-key
   SINRIC_APP_SECRET=your-sinric-app-secret
   API_TOKEN=any-strong-random-string
   ```

3. Edit `SERVICES_CONFIG` in `docker-compose.yml` — replace UUIDs with your real values:
   ```yaml
   SERVICES_CONFIG: >-
     [
       {"device_id": "YOUR-SINRIC-DEVICE-UUID", "type": "wifi_ssid",
        "name": "Guest WiFi", "config": {"wlan_id": "YOUR-UNIFI-WLAN-UUID"}}
     ]
   ```

4. Deploy:
   ```bash
   cd docker && docker compose up -d --build
   ```

5. Verify:
   ```bash
   curl http://nas-ip:8000/health
   curl http://nas-ip:8000/services
   ```

---

## Configuration Reference

### `SERVICES_CONFIG` JSON format

`SERVICES_CONFIG` is a JSON array. Each element defines one logical device.

```json
[
  {
    "device_id": "wifi-guest",
    "type": "wifi_ssid",
    "name": "Guest WiFi",
    "config": {
      "wlan_id": "YOUR-UNIFI-WLAN-UUID"
    }
  }
]
```

| Field | Type | Required | Description |
|---|---|---|---|
| `device_id` | string | **yes** | Sinric Pro device UUID — must match what you registered in the portal |
| `type` | string | **yes** | Handler type — currently `wifi_ssid`; add more by registering handlers |
| `name` | string | no | Human-readable label shown in log output and `/services` API |
| `config` | object | **yes** | Type-specific settings (see handler docs below) |

**`wifi_ssid` config keys:**

| Key | Required | Description |
|---|---|---|
| `wlan_id` | **yes** | UniFi WiFi broadcast UUID to control |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SINRIC_APP_KEY` | **yes** | — | Sinric Pro app key from portal |
| `SINRIC_APP_SECRET` | **yes** | — | Sinric Pro app secret from portal |
| `SERVICES_CONFIG` | **yes** | `[]` | JSON array of service definitions (see above) |
| `API_TOKEN` | **yes** | — | Shared secret for local protected endpoints (`X-API-Key` header) |
| `UNIFI_HOST` | for WiFi | `192.168.1.1` | UniFi controller hostname or IP |
| `UNIFI_API_KEY` | for WiFi | — | UniFi integration API key |
| `UNIFI_SITE_ID` | for WiFi | — | UniFi site UUID |
| `ALLOWED_HOSTS` | no | `127.0.0.1,172.16.0.0/12,`<br>`192.168.0.0/16,10.0.0.0/8` | Comma-separated IPs/CIDRs allowed to call local endpoints |

---

## API Endpoints

All endpoints are local-only (Docker binds to `127.0.0.1:8000` by default; use
SSH tunnel or Synology reverse proxy for LAN access).

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | none | Liveness check — always returns `{"status":"ok"}` |
| `GET` | `/services` | IP allowlist | List all registered services and their types |
| `GET` | `/service/{device_id}/details` | IP + `X-API-Key` | Return current state/details from the downstream API |
| `POST` | `/service/{device_id}/on` | IP + `X-API-Key` | Send `setPowerState On` to the handler |
| `POST` | `/service/{device_id}/off` | IP + `X-API-Key` | Send `setPowerState Off` to the handler |
| `POST` | `/service/{device_id}/toggle` | IP + `X-API-Key` | Read current state, flip it |

**Auth:**
- **IP allowlist** — request must come from an IP/CIDR in `ALLOWED_HOSTS`
- **`X-API-Key`** — pass your `API_TOKEN` value in the `X-API-Key` request header

**Example calls:**
```bash
# Check health (no auth)
curl http://nas-ip:8000/health

# List services (IP only)
curl http://nas-ip:8000/services

# Get state (IP + token)
curl http://nas-ip:8000/service/wifi-guest/details \
  -H "X-API-Key: $API_TOKEN"

# Turn on (IP + token)
curl -X POST http://nas-ip:8000/service/wifi-guest/on \
  -H "X-API-Key: $API_TOKEN"
```

---

## Adding New Service Types

See [docs/ADDING_NEW_SERVICES.md](../docs/ADDING_NEW_SERVICES.md) for a
complete walkthrough, including a full `GarageDoorHandler` example.

---

## Migrating from v2 (single-service)

If you previously used `SINRIC_DEVICE_ID` and `UNIFI_WLAN_ID`, see
[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for the env var mapping, before/after
compose examples, and updated endpoint paths.
