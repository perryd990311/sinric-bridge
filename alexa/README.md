# Alexa Integration – Sinric Pro Path

## Overview

Alexa controls a Sinric Pro virtual switch via Routines. Sinric Pro pushes the
event to your Synology container over an outbound WebSocket. **No inbound ports,
no public URL, no IFTTT.**

```
"Alexa, WiFi off"
        ↓
   Alexa Routine  (custom phrase)
        ↓
   Sinric Pro virtual switch  (Alexa discovers it as a smart device)
        ↓
   Outbound WebSocket (wss://, HMAC-signed)
        ↓
   Python service on Synology  →  UniFi API  →  SSID toggled
```

---

## Sinric Pro Account Setup

1. Register at [portal.sinric.pro](https://portal.sinric.pro) (free — 3 devices)
2. **Devices → Add Device**:
   - Name: `WiFi Toggle`
   - Type: **Switch**
3. Copy the **Device ID** from the device page
4. Go to **Credentials** → copy **App Key** and **App Secret**
5. Paste all three into your `docker/.env` file

---

## Link Sinric Pro to Alexa

1. Open the **Alexa app** → **Skills & Games** → search **Sinric Pro**
2. **Enable** the skill → sign in with your Sinric Pro account
3. Alexa will discover your **WiFi Toggle** device
4. Quick test: say **"Alexa, turn off WiFi Toggle"**

---

## Create Alexa Routines (Natural Phrases)

Routines let you map any phrase to the virtual switch — no "trigger" prefix needed.

### WiFi Off Routine

| Field | Value |
|---|---|
| **When** | Voice: `WiFi off` |
| **Action** | Smart Home → WiFi Toggle → **Off** |

### WiFi On Routine

| Field | Value |
|---|---|
| **When** | Voice: `WiFi on` |
| **Action** | Smart Home → WiFi Toggle → **On** |

Steps:
1. Alexa app → **More** → **Routines** → **+**
2. **When this happens** → **Voice** → type your phrase
3. **Add action** → **Smart Home** → **WiFi Toggle** → set power state
4. **Save**

---

## Security – Sinric Pro Path

| Layer | What It Does |
|---|---|
| **No inbound ports** | Service connects outbound — nothing exposed to the internet |
| **HMAC-signed WebSocket** | Every Sinric message is cryptographically signed with your App Secret; unsigned/tampered messages are rejected by the SDK |
| **TLS (wss://)** | WebSocket connection is encrypted end-to-end |
| **Localhost-only HTTP** | Docker binds port 8000 to `127.0.0.1` only |
| **IP allowlist** | HTTP endpoints reject non-RFC-1918 source IPs |
| **API key on local endpoints** | Even LAN requests require `X-API-Key` header |

### What You No Longer Need (vs. IFTTT Path)
- ~~Port 443 forwarded to Synology~~
- ~~DuckDNS hostname~~
- ~~Let's Encrypt certificate management~~
- ~~IFTTT account + applets~~
- ~~`VERIFY_ALEXA_SIG` flag~~
- ~~Public webhook URL~~

### Security Checklist
- [ ] Sinric App Secret stored in `.env`, not in compose YAML
- [ ] `.env` file permissions: `chmod 600 .env` (owner-read only)
- [ ] `.env` listed in `.gitignore`
- [ ] Strong unique password + MFA on your Sinric Pro account
- [ ] No router port forwarding to the Synology for this service
- [ ] API_TOKEN is a 32+ char random string
- [ ] UniFi controller port **not** forwarded — LAN access only

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Alexa can't find WiFi Toggle device | Re-enable Sinric Pro skill; re-run device discovery |
| "WiFi Toggle is not responding" | Container not running — check `docker compose ps` and logs |
| Routine doesn't fire | Verify the routine phrase and action in Alexa app |
| Voice works but SSID doesn't change | Check `UNIFI_WLAN_ID` in `.env`; check container logs for errors |
| Sinric connects then disconnects | App Key or App Secret is wrong — re-copy from Sinric portal |
