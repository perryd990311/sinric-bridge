# Home Automation – Multi-Service Voice Control

[![CI](https://github.com/perryd990311/sinric-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/perryd990311/sinric-bridge/actions/workflows/ci.yml)

> **v3.0.0** — Multi-service architecture. A single container manages any number of devices across multiple service types. See [RELEASE_NOTES.md](RELEASE_NOTES.md) for what's new.  
> Upgrading from v2? See the [Migration Guide](python-service/MIGRATION_GUIDE.md).

## Goal
Use Alexa voice commands to control smart-home devices (WiFi SSIDs, smart plugs, garage doors, etc.) via a single Python service running on a local Synology NAS — no cloud relay, no port forwarding.

## Architecture – Sinric Pro Path

```
"Alexa, WiFi off"
        ↓
   Alexa Routine (custom phrase)
        ↓
   Sinric Pro virtual switch  ← Alexa sees it as a smart-home device
        ↓
   Outbound WebSocket (HMAC-signed)  →  Synology NAS – Docker
                                         Python FastAPI container
                                         (manages N devices via SERVICES_CONFIG)
                                                  ↓
                                         Service Handler (e.g. WiFiSSIDHandler)
                                                  ↓
                                         UniFi Gateway REST API / other APIs
                                                  ↓
                                            Action performed
```

**No port forwarding. No public URL. No IFTTT.**

## Devices
| Device | Role |
|---|---|
| UniFi Gateway (UDM/USG) | WiFi controller – exposes REST API on LAN |
| Synology NAS + Docker | Hosts the Python service container |
| Amazon Alexa | Voice trigger via Routine → Sinric Pro virtual switch |

## Security Highlights
| Layer | Protection |
|---|---|
| **No inbound ports** | Sinric uses outbound WebSocket — nothing exposed to the internet |
| **HMAC-signed messages** | Sinric SDK validates every message with your app secret |
| **Local-only HTTP** | Docker binds port 8000 to `127.0.0.1` — unreachable from WAN |
| **IP allowlist** | HTTP endpoints reject requests from outside RFC-1918 ranges |
| **API key auth** | Local endpoints require `X-API-Key` header |
| **Non-root container** | Service runs as unprivileged user inside Docker |
| **Read-only filesystem** | Container filesystem is immutable — no tampering |
| **No privilege escalation** | `no-new-privileges` security option enforced |
| **Secrets in `.env` file** | Credentials never hardcoded in compose YAML |

## REST API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/service/{device_id}/on` | Turn device on |
| `POST` | `/service/{device_id}/off` | Turn device off |
| `POST` | `/service/{device_id}/toggle` | Toggle device state |
| `GET`  | `/service/{device_id}/details` | Device details |
| `GET`  | `/services` | List all registered services and state |

All endpoints require `X-API-Key` and are restricted to local-network access.

## Folder Structure
```
home-automation/
├── README.md
├── RELEASE_NOTES.md
├── copilot_instructions.md          # Full Sinric Pro setup guide ← START HERE
├── verify_core_imports.py           # Smoke-test for core package imports
├── docs/
│   ├── setup.md                     # Step-by-step setup
│   ├── ADDING_NEW_SERVICES.md       # How to add a new device type
│   └── unifi_api_responses.md       # UniFi API reference
├── python-service/                  # Python FastAPI + Sinric Pro WebSocket client
│   ├── main.py
│   ├── MIGRATION_GUIDE.md           # v2 → v3 upgrade guide
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── services/                    # Service handlers
│   │   ├── base_handler.py          # ServiceHandler abstract base class
│   │   └── wifi_ssid_handler.py     # WiFiSSIDHandler implementation
│   ├── core/                        # Shared utilities
│   │   ├── fastapi_helpers.py
│   │   ├── auth/                    # API key authentication
│   │   ├── utils/                   # async, crypto, http, json, logging, network
│   │   └── websocket/               # Auto-reconnect WebSocket client
│   └── examples/                    # Example configs and compose files
├── docker/                          # docker-compose.yml + .env.example
└── unifi/                           # UniFi API reference
```

## Quick Start
1. Read [`copilot_instructions.md`](copilot_instructions.md) – the complete setup guide
2. Create a free [Sinric Pro](https://portal.sinric.pro) account and one virtual **Switch** per device
3. Copy `docker/.env.example` → `.env`, fill in your secrets and configure `SERVICES_CONFIG`:
   ```yaml
   SERVICES_CONFIG: >-
     [
       {"device_id": "abc-123", "type": "wifi_ssid",
        "name": "Guest WiFi", "config": {"wlan_id": "wlan-uuid-here"}}
     ]
   ```
4. Deploy on Synology: `cd /volume1/docker/sinric-bridge && docker compose up -d`
5. Link Sinric Pro to Alexa, create a Routine
6. Say **"Alexa, WiFi off"**

See [`docs/setup.md`](docs/setup.md) for detailed steps.

## Extending the Service
To add a new device type (garage door, smart plug, sensor, etc.) implement the `ServiceHandler` abstract base class and register it. See [`docs/ADDING_NEW_SERVICES.md`](docs/ADDING_NEW_SERVICES.md) for a step-by-step guide.
