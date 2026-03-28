# Middleware: Python FastAPI + Sinric Pro

## Current Setup – Python FastAPI with Sinric Pro WebSocket

The Python FastAPI service (`python-service/`) integrates two communication channels:

1. **Sinric Pro WebSocket (primary)** — receives switch events from Alexa via Sinric Pro
2. **Local HTTP API (secondary)** — for manual control and health checks from LAN

### Why This Stack

| Choice | Reason |
|---|---|
| **Sinric Pro** | Outbound WebSocket — no port forwarding, no public URL, no IFTTT dependency |
| **Python FastAPI** | Lightweight (~80 MB image), easy to extend, good async support |
| **Single container** | One process handles both WebSocket and HTTP — simple to deploy and monitor |

### Architecture

```
Alexa Routine  →  Sinric Pro (cloud)  →  WebSocket (outbound, HMAC-signed)
                                              ↓
                                     Python FastAPI container
                                              ↓
                                     UniFi Gateway REST API
```

### Sinric Pro Integration
- `sinricpro` SDK connects outbound to `wss://ws.sinric.pro`
- Messages are HMAC-signed with your App Secret — tampered messages are rejected
- Runs in a daemon thread alongside the FastAPI server
- Receives `powerState` callbacks when the virtual switch is toggled

### Local HTTP Endpoints
| Endpoint | Auth | Access | Action |
|---|---|---|---|
| `GET /health` | None | Any | Health check |
| `POST /wifi/on` | API key + IP allowlist | LAN only | Enable SSID |
| `POST /wifi/off` | API key + IP allowlist | LAN only | Disable SSID |
| `POST /wifi/toggle` | API key + IP allowlist | LAN only | Flip SSID state |

### Security Layers
| Layer | Purpose |
|---|---|
| No inbound ports | Nothing exposed to internet |
| HMAC message signing | Only messages signed with your secret are processed |
| TLS WebSocket (`wss://`) | Encrypted channel to Sinric cloud |
| Localhost port binding | Docker binds to `127.0.0.1` only |
| IP allowlist | HTTP endpoints reject non-private IPs |
| API key header | Local endpoints require `X-API-Key` |
| Non-root container | Runs as unprivileged user |
| Read-only filesystem | Immutable container — can't be tampered |
| No privilege escalation | `no-new-privileges` Docker security option |

See [`../python-service/main.py`](../python-service/main.py) for the implementation.
