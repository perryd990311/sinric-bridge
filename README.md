# Home Automation – WiFi SSID Voice Control

## Goal
Use an Alexa voice command to toggle a WiFi SSID on/off via the UniFi gateway API.

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
                                                  ↓
                                         UniFi Gateway REST API
                                                  ↓
                                            SSID disabled
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

## Folder Structure
```
home-automation/
├── copilot_instructions.md  # Full Sinric Pro setup guide ← START HERE
├── docs/
│   ├── setup.md             # Step-by-step setup
│   └── middleware-comparison.md
├── python-service/          # Python FastAPI + Sinric Pro WebSocket client
├── docker/                  # docker-compose.yml + .env.example
├── unifi/                   # UniFi API reference
└── alexa/                   # Alexa Routine setup
```

## Quick Start
1. Read [`copilot_instructions.md`](copilot_instructions.md) – the complete setup guide
2. Create a free Sinric Pro account and virtual switch
3. Copy `docker/.env.example` → `docker/.env` and fill in secrets
4. Deploy: `cd docker && docker compose up -d`
5. Link Sinric Pro to Alexa, create a Routine
6. Say **"Alexa, WiFi off"**

See [`docs/setup.md`](docs/setup.md) for detailed steps.
