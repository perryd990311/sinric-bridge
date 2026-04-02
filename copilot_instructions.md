# Sinric Pro Setup Guide – Alexa → UniFi WiFi Toggle

## Overview

This guide sets up the complete voice-to-WiFi-toggle chain using Sinric Pro.
**No port forwarding. No public URL. No IFTTT.**

```
"Alexa, WiFi off"
        ↓
   Alexa Routine  (custom phrase — no "trigger" prefix)
        ↓
   Sinric Pro virtual switch  (Alexa sees it as a smart device)
        ↓
   Outbound WebSocket (HMAC-signed) →  Synology NAS container
        ↓
   Python FastAPI  →  UniFi API
        ↓
   SSID disabled
```

---

## Why Sinric Pro over IFTTT

| | IFTTT (old) | Sinric Pro (current) |
|---|---|---|
| Voice phrase | "Alexa, **trigger** WiFi off" | "Alexa, WiFi off" |
| Latency | 1–15 sec (free tier) | **< 1 sec** |
| Port forwarding | **Required** (443 → Synology) | **None** |
| DuckDNS / certs | Required | **Not needed** |
| Internet exposure | Webhook URL public | **Nothing exposed** |
| Free tier limit | 2 applets total | 3 devices |

---

## Prerequisites

| Item | Status |
|---|---|
| Sinric Pro account (free — 3 devices) | Required |
| Amazon Alexa + Echo device | Required |
| Synology NAS with Docker/Container Manager | Required |
| UniFi gateway (UDM / USG) on LAN | Required |

---

## Step 1 – Gather UniFi IDs + API Key

```bash
# List sites
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"

# Read one WiFi broadcast
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites/YOUR_SITE_ID/wifi/broadcasts/YOUR_WLAN_ID" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"
```

Copy your `site` UUID and target `wifi broadcast` UUID into `.env`.

---

## Step 2 – Create the Sinric Pro Virtual Switch

1. Sign up at [portal.sinric.pro](https://portal.sinric.pro) (free)
2. Go to **Devices** → **Add Device**
3. Fill in:
   - **Device Name:** `WiFi Toggle`
   - **Device Type:** **Switch**
   - **Description:** Controls UniFi SSID
4. Click **Save** → copy the **Device ID**
5. Go to **Credentials** → copy your **App Key** and **App Secret**

> **Security:** Your App Secret is used to HMAC-sign every WebSocket message.
> Treat it like a password — never commit it to source control.

---

## Step 3 – Configure Secrets

```bash
cd /volume1/docker/home-automation/docker
cp .env.example .env
```

Edit `.env` with your values:

```ini
UNIFI_HOST=192.168.1.1
UNIFI_API_KEY=your-unifi-api-key
UNIFI_SITE_ID=paste-site-id-here

SINRIC_APP_KEY=paste-app-key-here
SINRIC_APP_SECRET=paste-app-secret-here

SERVICES_CONFIG=[{"device_id":"paste-sinric-device-id-here","type":"wifi_ssid","name":"WiFi Toggle","config":{"wlan_id":"paste-unifi-wlan-id-here"}}]

API_TOKEN=generate-a-strong-token
```

Generate `API_TOKEN`:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Never commit `.env`** — it's already in `.env.example` as a template without secrets.

---

## Step 4 – Deploy the Container

```bash
cd /volume1/docker/sinric-bridge
docker compose up -d

# Verify:
docker compose logs -f sinric-bridge
# Look for: "Starting Sinric Pro WebSocket client"
```

Health check:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Step 5 – Link Sinric Pro to Alexa

1. Open the **Alexa app** on your phone
2. Go to **Skills & Games** → search **Sinric Pro** → **Enable**
3. Sign in with your Sinric Pro account
4. Alexa will discover your **WiFi Toggle** device
5. Test: say **"Alexa, turn off WiFi Toggle"**

---

## Step 6 – Create Alexa Routines (Custom Phrases)

Routines let you use natural phrases like "WiFi off" instead of "turn off WiFi Toggle".

### WiFi Off Routine
1. Alexa app → **More** → **Routines** → **+**
2. **When:** Voice → enter `WiFi off`
3. **Action:** Smart Home → WiFi Toggle → **Off**
4. Save

### WiFi On Routine
Same as above but phrase `WiFi on` → action **On**

### Test
Say **"Alexa, WiFi off"** — the SSID should disable within ~1 second.

---

## Network & Auth Security

### Attack Surface Comparison

| Vector | IFTTT (old) | Sinric Pro (current) |
|---|---|---|
| Inbound ports open | 443 (public) | **None** |
| Public DNS record | DuckDNS hostname | **None** |
| TLS certificate to manage | Let's Encrypt | **None** (Sinric handles it) |
| Service reachable from internet | Yes | **No** |

### Security Layers in This Setup

| Layer | What It Does | Config |
|---|---|---|
| **No inbound ports** | Nothing to scan, probe, or exploit from outside | Architecture — Sinric WebSocket is outbound |
| **HMAC message signing** | Every Sinric message is signed with your App Secret; SDK rejects unsigned/tampered messages | Automatic via `sinricpro` SDK |
| **TLS WebSocket** | Sinric connection is `wss://` (encrypted) | Automatic via SDK |
| **Localhost-only binding** | Docker port 8000 bound to `127.0.0.1` — not reachable from WAN or other LAN hosts | `ports: "127.0.0.1:8000:8000"` in compose |
| **IP allowlist** | HTTP endpoints reject requests from outside RFC-1918 private ranges | `ALLOWED_HOSTS` env var |
| **API key auth** | Local HTTP endpoints require `X-API-Key` header | `API_TOKEN` env var |
| **Non-root container** | Process runs as UID 1000, not root | `USER appuser` in Dockerfile |
| **Read-only filesystem** | Container filesystem is immutable — cannot be tampered | `read_only: true` in compose |
| **No privilege escalation** | Prevents `setuid`/capabilities exploits within container | `no-new-privileges:true` in compose |
| **Secrets in `.env`** | Credentials never appear in compose YAML or source control | `.env` file loaded by compose |

### Credential Rotation Checklist
- [ ] Sinric App Secret: regenerate in Sinric portal → update `.env` → restart container
- [ ] UniFi API key: rotate in UniFi API settings → update `.env` → restart container
- [ ] API_TOKEN: regenerate with `secrets.token_urlsafe(32)` → update `.env` → restart
- [ ] Rotate all credentials if NAS is compromised or `.env` file is leaked

### What to **Never** Do
- **Never** forward port 8000 (or any port) to the internet for this service
- **Never** commit `.env` to Git — add it to `.gitignore`
- **Never** hardcode credentials in `docker-compose.yml` or `main.py`
- **Never** share your Sinric App Secret — it's the signing key for all messages

---

## Troubleshooting

| Symptom | Check |
|---|---|
| "Starting Sinric Pro WebSocket client" not in logs | `SINRIC_APP_KEY` or `SINRIC_APP_SECRET` missing, or `SERVICES_CONFIG` is empty/invalid JSON |
| Sinric connects but Alexa doesn't find device | Re-run Alexa device discovery; ensure Sinric Pro skill is enabled |
| Alexa says "WiFi Toggle is not responding" | Check container is running: `docker compose ps`; check logs for errors |
| SSID doesn't toggle | `UNIFI_WLAN_ID` is blank or wrong — re-run the WLAN ID lookup |
| `403 Access denied — local network only` | Trying to access HTTP endpoints from outside allowed IP ranges |
| `403 Invalid API key` on manual `curl` | `X-API-Key` header doesn't match `API_TOKEN` in `.env` |
| Container won't start | Check `.env` has all required vars — compose will error on missing `${VAR:?}` |
| Health check failing | Verify port 8000 is accessible on localhost: `curl http://localhost:8000/health` |

---

## Manual Override (LAN Only)

The HTTP endpoints still work for manual control or scripts — but only from the local network:

```bash
# From the Synology itself or another LAN machine:
curl -X POST http://YOUR_SYNOLOGY_IP:8000/wifi/off \
  -H "X-API-Key: your-API_TOKEN-value"

curl -X POST http://YOUR_SYNOLOGY_IP:8000/wifi/on \
  -H "X-API-Key: your-API_TOKEN-value"

curl -X POST http://YOUR_SYNOLOGY_IP:8000/wifi/toggle \
  -H "X-API-Key: your-API_TOKEN-value"
```

> These will only work from IPs within the `ALLOWED_HOSTS` ranges.
