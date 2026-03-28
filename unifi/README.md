# UniFi API Reference

Used by the Python service to enable/disable a WiFi SSID.
See [`../copilot_instructions.md`](../copilot_instructions.md) for where this fits in the full setup.

> **Security note:** The UniFi API is only accessed over the LAN. The self-signed
> certificate is acceptable here because the gateway is trusted local infrastructure.
> **Never** expose the UniFi controller port to the internet.

---

## Step 1 – Gather IDs for Integration API

Run these commands from any machine on your LAN:

```bash
# 1. List sites and copy your site UUID
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"

# 2. Read your target WiFi broadcast by UUID
curl -sk -X GET "https://192.168.1.1/proxy/network/integration/v1/sites/YOUR_SITE_ID/wifi/broadcasts/YOUR_WLAN_ID" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Accept: application/json"
```

Set these values in `docker/.env`:
- `UNIFI_API_KEY`
- `UNIFI_SITE_ID`
- `UNIFI_WLAN_ID`

---

## WLAN Toggle Endpoint (Integration API)

```
PUT /proxy/network/integration/v1/sites/{site_id}/wifi/broadcasts/{wlan_id}
```

Disable SSID:
```json
{ "enabled": false }
```

Enable SSID:
```json
{ "enabled": true }
```

---

## Device Notes

| Setting | Value |
|---|---|
| Default gateway IP | `192.168.1.1` |
| Auth header | `X-API-KEY: YOUR_API_KEY` |
| Sites endpoint | `/proxy/network/integration/v1/sites` |
| WiFi endpoint | `/proxy/network/integration/v1/sites/{site_id}/wifi/broadcasts/{wlan_id}` |
| Self-signed cert | Use `-sk` flags in curl; Python service skips verification automatically |

---

## Manual Test – Toggle SSID Without the Python Service

```bash
# Disable SSID
curl -sk -X PUT "https://192.168.1.1/proxy/network/integration/v1/sites/YOUR_SITE_ID/wifi/broadcasts/YOUR_WLAN_ID" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Enable SSID
curl -sk -X PUT "https://192.168.1.1/proxy/network/integration/v1/sites/YOUR_SITE_ID/wifi/broadcasts/YOUR_WLAN_ID" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```
