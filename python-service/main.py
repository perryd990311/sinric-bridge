"""
WiFi SSID Toggle Service — Sinric Pro Edition

Receives Sinric Pro switch events via outbound WebSocket and toggles a
UniFi SSID on or off.  No inbound ports, no IFTTT, no public URL required.

Architecture:
  Alexa Routine  →  Sinric Pro virtual switch  →  WebSocket (outbound)
       →  this service  →  UniFi Gateway REST API  →  SSID enabled/disabled

Environment variables:
    UNIFI_HOST        - UniFi controller IP/hostname (default: 192.168.1.1)
    UNIFI_API_KEY     - UniFi API key for integration endpoints
    UNIFI_SITE_ID     - UniFi site UUID
    UNIFI_WLAN_ID     - WiFi broadcast UUID to toggle
  SINRIC_APP_KEY    - Sinric Pro app key (from portal)
  SINRIC_APP_SECRET - Sinric Pro app secret (from portal)
  SINRIC_DEVICE_ID  - Sinric Pro virtual switch device ID
  API_TOKEN         - Shared secret for local health/manual endpoints
  ALLOWED_HOSTS     - Comma-separated IPs allowed to hit local endpoints
                      (default: 127.0.0.1,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8)
"""

import os
import asyncio
import base64
import hashlib
import hmac
import time
import urllib.request
import urllib.error
import json
import ssl
import logging
import ipaddress
from contextlib import asynccontextmanager
from threading import Thread

import websockets
from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("wifi-toggle")

# ── Configuration ────────────────────────────────────────────────────────────
UNIFI_HOST        = os.getenv("UNIFI_HOST", "192.168.1.1")
UNIFI_API_KEY     = os.getenv("UNIFI_API_KEY", "")
UNIFI_SITE_ID     = os.getenv("UNIFI_SITE_ID") or os.getenv("UNIFI_SITE", "")
UNIFI_WLAN_ID     = os.getenv("UNIFI_WLAN_ID", "")
SINRIC_APP_KEY    = os.getenv("SINRIC_APP_KEY", "")
SINRIC_APP_SECRET = os.getenv("SINRIC_APP_SECRET", "")
SINRIC_DEVICE_ID  = os.getenv("SINRIC_DEVICE_ID", "")
API_TOKEN         = os.getenv("API_TOKEN", "")
ALLOWED_HOSTS     = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8",
)

# Parse allowed networks/IPs for local endpoint access control
_allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
for entry in ALLOWED_HOSTS.split(","):
    entry = entry.strip()
    if entry:
        try:
            _allowed_networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid ALLOWED_HOSTS entry: %s", entry)


# ── Local network access control ────────────────────────────────────────────
def _is_allowed_ip(client_ip: str) -> bool:
    """Return True if client_ip falls within any configured network."""
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(addr in net for net in _allowed_networks)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_token(key: str = Security(api_key_header)):
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured")
    if key != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key


def verify_local_network(request: Request):
    """Block requests from outside the local network."""
    client_ip = request.client.host if request.client else "unknown"
    if not _is_allowed_ip(client_ip):
        logger.warning("Blocked request from non-local IP: %s", client_ip)
        raise HTTPException(status_code=403, detail="Access denied — local network only")


# ── UniFi API (LAN-only, self-signed cert) ───────────────────────────────────
# UniFi controllers use self-signed certs by default.  The connection stays
# on the LAN so this is acceptable — the gateway is trusted infrastructure.
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _unifi_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Call the UniFi integration API using an X-API-KEY header."""
    if not UNIFI_API_KEY:
        raise ValueError("UNIFI_API_KEY not set")

    url = f"https://{UNIFI_HOST}{path}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-API-KEY": UNIFI_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ssl_ctx))
    try:
        with opener.open(req) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        logger.error(
            "UniFi %s %s → HTTP %s: %s",
            method, path, status, body[:500].decode(errors="replace"),
        )
        raise

    if not body:
        return {}

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        logger.error(
            "UniFi %s %s → HTTP %s non-JSON body: %s",
            method, path, status, body[:500].decode(errors="replace"),
        )
        raise


def _get_wlan_path() -> str:
    if not UNIFI_SITE_ID:
        raise ValueError("UNIFI_SITE_ID not set")
    if not UNIFI_WLAN_ID:
        raise ValueError("UNIFI_WLAN_ID not set")
    return f"/proxy/network/integration/v1/sites/{UNIFI_SITE_ID}/wifi/broadcasts/{UNIFI_WLAN_ID}"


def _extract_wlan_payload(data: dict) -> dict:
    """Normalize UniFi GET response into the writable WiFi broadcast document.

    The integration API returns the broadcast object directly (no wrapper).
    Strip read-only fields that the PUT endpoint does not accept.
    """
    # Unwrap legacy/alternative response shapes just in case
    if isinstance(data.get("data"), list) and data["data"]:
        data = data["data"][0]
    elif isinstance(data.get("data"), dict):
        data = data["data"]

    # Remove fields present in GET responses that are not valid PUT request body fields
    _read_only = {"id", "metadata"}
    return {k: v for k, v in data.items() if k not in _read_only}


def set_wlan_state(enabled: bool) -> dict:
    wlan = _extract_wlan_payload(get_wlan_details())
    wlan["enabled"] = enabled
    return _unifi_request("PUT", _get_wlan_path(), wlan)


def get_wlan_details() -> dict:
    """Return the current WiFi broadcast configuration."""
    return _unifi_request("GET", _get_wlan_path())


def get_wlan_state() -> bool:
    """Return current SSID enabled state."""
    wlan = _extract_wlan_payload(get_wlan_details())
    return bool(wlan["enabled"])


# ── Sinric Pro WebSocket (raw protocol, no SDK) ──────────────────────────────
# Sinric Pro uses a plain WebSocket with HMAC-SHA256 message signing.
# This avoids any SDK version dependency and gives full control over the loop.

SINRIC_WS_URL = "wss://ws.sinric.pro"


def _sinric_sign(payload: dict) -> str:
    """Compute Sinric-compatible Base64 HMAC over payload JSON.

    Official SinricPro SDK behavior:
    - sign only the `payload`
    - use compact JSON separators
    - use sort_keys=False
    - encode digest as Base64 (not hex)
    """
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    digest = hmac.new(
        SINRIC_APP_SECRET.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _sinric_verify(msg: dict) -> bool:
    """Verify incoming Sinric payload signature (Base64 HMAC)."""
    remote_hmac = (msg.get("signature") or {}).get("HMAC") or ""
    payload = msg.get("payload")
    if not remote_hmac or not isinstance(payload, dict):
        return False
    return hmac.compare_digest(remote_hmac, _sinric_sign(payload))


async def _sinric_loop():
    """Maintain a persistent, auto-reconnecting WebSocket to Sinric Pro."""
    headers = [
        ("appKey", SINRIC_APP_KEY),
        ("deviceIds", SINRIC_DEVICE_ID),
        ("platform", "python"),
        ("version", "3.1.0"),
    ]
    while True:
        try:
            async with websockets.connect(
                SINRIC_WS_URL,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10,
            ) as ws:
                logger.info("Sinric Pro WebSocket connected")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        if not _sinric_verify(msg):
                            logger.warning("Ignoring Sinric message with invalid signature")
                            continue
                        payload = msg.get("payload", {})
                        if payload.get("type") != "request":
                            continue
                        action = payload.get("action", "")
                        device_id = payload.get("deviceId", "")
                        value = payload.get("value", {})

                        if action == "setPowerState" and device_id == SINRIC_DEVICE_ID:
                            state = value.get("state", "")
                            logger.info(
                                "Sinric setPowerState: device=%s state=%s",
                                device_id, state,
                            )
                            try:
                                set_wlan_state(state.lower() == "on")
                                success = True
                            except Exception:
                                logger.exception("Failed to set WLAN state")
                                success = False

                            # Match official Sinric SDK response shape.
                            resp_payload = {
                                "action": payload.get("action", "setPowerState"),
                                "clientId": payload.get("clientId", SINRIC_APP_KEY),
                                "createdAt": int(time.time()),
                                "deviceId": payload.get("deviceId", device_id),
                                "message": "OK" if success else "Request failed",
                                "replyToken": payload.get("replyToken", ""),
                                "scope": payload.get("scope", "device"),
                                "success": success,
                                "type": "response",
                                "value": payload.get("value", {"state": state}),
                            }
                            if "instanceId" in payload:
                                resp_payload["instanceId"] = payload["instanceId"]

                            await ws.send(json.dumps({
                                "header": msg.get("header", {
                                    "payloadVersion": 2,
                                    "signatureVersion": 1,
                                }),
                                "payload": resp_payload,
                                "signature": {"HMAC": _sinric_sign(resp_payload)},
                            }))
                    except Exception:
                        logger.exception("Error handling Sinric Pro message")

        except Exception as exc:
            logger.warning(
                "Sinric Pro disconnected (%s) — reconnecting in 5s", exc
            )
            await asyncio.sleep(5)


def _run_sinric():
    """Run the Sinric Pro WebSocket loop in a background thread."""
    if not all([SINRIC_APP_KEY, SINRIC_APP_SECRET, SINRIC_DEVICE_ID]):
        logger.error(
            "Sinric Pro not configured — set SINRIC_APP_KEY, "
            "SINRIC_APP_SECRET, and SINRIC_DEVICE_ID"
        )
        return

    logger.info("Starting Sinric Pro WebSocket client (device: %s)", SINRIC_DEVICE_ID)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_sinric_loop())



# ── FastAPI lifecycle ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Sinric in a daemon thread so it doesn't block uvicorn
    sinric_thread = Thread(target=_run_sinric, daemon=True, name="sinric-pro")
    sinric_thread.start()
    logger.info("Service started — Sinric Pro WebSocket + local API ready")
    yield
    logger.info("Service shutting down")


app = FastAPI(title="UniFi WiFi Toggle", version="2.0.0", lifespan=lifespan)


# ── Local-only endpoints (for manual/debug use from LAN) ────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/wifi/details")
async def wifi_details(
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Return raw WiFi broadcast details from UniFi (local network only)."""
    try:
        result = get_wlan_details()
        logger.info("Manual /wifi/details from %s", request.client.host)
        return {"details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/wifi/on")
async def wifi_on(
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Enable the configured SSID (local network only)."""
    try:
        result = set_wlan_state(True)
        logger.info("Manual /wifi/on from %s", request.client.host)
        return {"action": "on", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/wifi/off")
async def wifi_off(
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Disable the configured SSID (local network only)."""
    try:
        result = set_wlan_state(False)
        logger.info("Manual /wifi/off from %s", request.client.host)
        return {"action": "off", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/wifi/toggle")
async def wifi_toggle(
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Auto-detect current state and flip it (local network only)."""
    try:
        current = get_wlan_state()
        result = set_wlan_state(not current)
        logger.info("Manual /wifi/toggle from %s: %s→%s", request.client.host, current, not current)
        return {"action": "toggle", "was": current, "now": not current, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
