# Setup Guide

## Prerequisites

| Requirement | Notes |
|---|---|
| Synology NAS with Docker / Container Manager | Package Center → Docker or Container Manager |
| UniFi Dream Machine or USG | Firmware with API enabled (default) |
| Amazon Echo device | Any Echo model |
| Sinric Pro account | [portal.sinric.pro](https://portal.sinric.pro) – free tier (3 devices) |

> **Not required:** port forwarding, DuckDNS, public URL, IFTTT, TLS certificates.
> Sinric Pro uses an outbound WebSocket — your NAS initiates the connection.

---

## Step 1 – Gather UniFi IDs + API Key

You need a UniFi API key plus these IDs:
- Site UUID (`UNIFI_SITE_ID`)
- WiFi broadcast UUID (`UNIFI_WLAN_ID`)

```bash
# List sites
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"

# Get one WiFi broadcast by id (example shape)
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites/YOUR_SITE_ID/wifi/broadcasts/YOUR_WLAN_ID" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"
```

See [`../unifi/README.md`](../unifi/README.md) for full API reference.

---

## Step 2 – Create the Sinric Pro Virtual Switch

1. Sign up at [portal.sinric.pro](https://portal.sinric.pro) (free)
2. **Devices → Add Device**:
   - Name: `WiFi Toggle`
   - Type: **Switch**
3. Save → copy the **Device ID**
4. **Credentials** → copy **App Key** and **App Secret**

---

## Step 3 – Configure Secrets

1. Copy the project folder to your Synology (e.g. `/volume1/docker/home-automation/`)
2. Create the `.env` file from the template:

```bash
cd /volume1/docker/home-automation/docker
cp .env.example .env
chmod 600 .env    # Owner-read only — protect credentials
```

3. Edit `.env` with your values:

```ini
UNIFI_HOST=192.168.1.1
UNIFI_API_KEY=your-unifi-api-key
UNIFI_SITE_ID=paste-site-id-here

SINRIC_APP_KEY=paste-app-key-here
SINRIC_APP_SECRET=paste-app-secret-here

SERVICES_CONFIG=[{"device_id":"paste-sinric-device-id-here","type":"wifi_ssid","name":"WiFi Toggle","config":{"wlan_id":"paste-unifi-wlan-id-here"}}]

API_TOKEN=paste-generated-token-here
```

Generate a strong `API_TOKEN`:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Security:** Never commit `.env` to version control. Add it to `.gitignore`.

---

## Step 4 – Deploy the Container

```bash
cd /volume1/docker/home-automation/docker
docker compose up -d

# Verify:
docker compose logs -f sinric-bridge
# Look for: "Starting Sinric Pro WebSocket client"
# Look for: "Service started — Sinric Pro WebSocket + local API ready"
```

Health check:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Step 5 – Link Sinric Pro to Alexa

1. Open **Alexa app** → **Skills & Games** → search **Sinric Pro** → **Enable**
2. Sign in with your Sinric Pro credentials
3. Alexa will auto-discover the **WiFi Toggle** device
4. Quick test: "Alexa, turn off WiFi Toggle"

---

## Step 6 – Create Alexa Routines

For natural voice commands (no "turn off device-name" phrasing):

### WiFi Off Routine
1. Alexa app → **More** → **Routines** → **+**
2. **When:** Voice → `WiFi off`
3. **Action:** Smart Home → WiFi Toggle → **Off**
4. Save

### WiFi On Routine
Same but phrase `WiFi on` → action **On**

---

## Step 7 – Test End to End

**Voice test:**
Say **"Alexa, WiFi off"** — SSID should disable within ~1 second.

**Manual LAN test:**
```bash
curl -X POST http://localhost:8000/wifi/off \
  -H "X-API-Key: your-API_TOKEN-value"
# Expected: {"action":"off","result":{...}}
```

---

## Security Hardening

This setup has **no inbound attack surface** by design. Additional hardening:

| Measure | How |
|---|---|
| File permissions | `chmod 600 docker/.env` |
| Git exclusion | Add `.env` to `.gitignore` |
| Non-root container | Already configured in Dockerfile |
| Read-only filesystem | Already configured in docker-compose.yml |
| No privilege escalation | Already configured in docker-compose.yml |
| Localhost-only port binding | `127.0.0.1:8000:8000` — not reachable from WAN |
| IP allowlist on HTTP endpoints | `ALLOWED_HOSTS` defaults to RFC-1918 private ranges |
| Sinric HMAC signing | Automatic — SDK validates every message |
| Router audit | Confirm **no** port forwarding rules point to the Synology for this service |
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| `curl /health` times out | Container not running — `docker compose ps` |
| `403 Invalid API key` | `X-API-Key` doesn't match `API_TOKEN` in `.env` |
| SSID doesn't change | `wlan_id` in `SERVICES_CONFIG` is blank or wrong — rerun Step 1 |
| Sinric connects but no messages routed | `device_id` in `SERVICES_CONFIG` doesn't match Sinric portal UUID |
| Alexa says device not responding | Check `docker compose logs sinric-bridge`; verify Sinric Pro skill is linked |
| Service starts but no handlers registered | `SERVICES_CONFIG` is empty or invalid JSON — check for syntax errors |
