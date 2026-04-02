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
  SINRIC_APP_KEY    - Sinric Pro app key (from portal)
  SINRIC_APP_SECRET - Sinric Pro app secret (from portal)
  SERVICES_CONFIG  - JSON array of service definitions, e.g.:
                     [{"device_id":"wifi-guest","type":"wifi_ssid",
                       "name":"Guest WiFi","config":{"wlan_id":"uuid"}}]
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
import json
import logging
import ipaddress
from contextlib import asynccontextmanager
from threading import Thread

import websockets
from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security import APIKeyHeader
from services.wifi_ssid_handler import WiFiSSIDHandler

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
SINRIC_APP_KEY    = os.getenv("SINRIC_APP_KEY", "")
SINRIC_APP_SECRET = os.getenv("SINRIC_APP_SECRET", "")
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


# ── Multi-service registry ───────────────────────────────────────────────────
_raw_services = os.getenv("SERVICES_CONFIG", "[]")
try:
    _services_list = json.loads(_raw_services)
except json.JSONDecodeError as e:
    logger.error("SERVICES_CONFIG is not valid JSON: %s", e)
    _services_list = []

# Build registry: {device_id → {type, name, config}}
SERVICES: dict = {}
for _svc in _services_list:
    _did = _svc.get("device_id", "").strip()
    if not _did:
        logger.warning("Skipping service entry with missing device_id: %s", _svc)
        continue
    if _did in SERVICES:
        logger.warning("Duplicate device_id %r — skipping second entry", _did)
        continue
    if not _svc.get("type") or "config" not in _svc or not isinstance(_svc.get("config"), dict):
        logger.warning("Service %r has invalid or missing 'type'/'config' — skipping", _did)
        continue
    SERVICES[_did] = {
        "type": _svc["type"],
        "name": _svc.get("name", _did),
        "config": _svc["config"],
    }

if not SERVICES:
    logger.warning(
        "No services configured — set SERVICES_CONFIG env var as a JSON array. "
        'Example: [{"device_id":"wifi-guest","type":"wifi_ssid",'
        '"name":"Guest WiFi","config":{"wlan_id":"uuid-here"}}]'
    )

# Detect legacy single-service env vars and warn
_legacy_device_id = os.getenv("SINRIC_DEVICE_ID")
_legacy_wlan_id = os.getenv("UNIFI_WLAN_ID")
if _legacy_device_id or _legacy_wlan_id:
    logger.error(
        "Detected legacy env vars (SINRIC_DEVICE_ID=%s, UNIFI_WLAN_ID=%s). "
        "These are no longer supported. "
        "Migrate to SERVICES_CONFIG JSON array. See examples/services-config.json.",
        "set" if _legacy_device_id else "not set",
        "set" if _legacy_wlan_id else "not set",
    )


# ── Handler registry ─────────────────────────────────────────────────────────
_SERVICE_HANDLER_CLASSES: dict = {
    "wifi_ssid": WiFiSSIDHandler,
    # Add more service types here as new handlers are created
}


def _build_handlers() -> dict:
    """Instantiate a ServiceHandler for each configured service."""
    handlers: dict = {}
    for device_id, svc in SERVICES.items():
        cls = _SERVICE_HANDLER_CLASSES.get(svc["type"])
        if cls is None:
            logger.warning(
                "No handler registered for service type %r (device %s) — skipping",
                svc["type"], device_id,
            )
            continue
        handler = cls(device_id, svc["type"], svc["config"])
        handlers[device_id] = handler
        logger.info("Registered handler: %s (%s) → %s", device_id, svc["name"], svc["type"])
    return handlers


HANDLERS: dict = _build_handlers()


async def _verify_handlers():
    """Verify all handler configurations during startup (async-safe)."""
    to_remove = []
    for device_id, handler in HANDLERS.items():
        try:
            ok = await handler.verify_configuration()
            if not ok:
                logger.warning("Handler '%s' failed verification — will be skipped", device_id)
                to_remove.append(device_id)
        except Exception:
            logger.exception("Handler '%s' verification raised error — will be skipped", device_id)
            to_remove.append(device_id)
    for device_id in to_remove:
        del HANDLERS[device_id]


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
    device_list = ",".join(HANDLERS.keys()) if HANDLERS else ""
    headers = [
        ("appKey", SINRIC_APP_KEY),
        ("deviceIds", device_list),
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
                logger.info("Sinric Pro WebSocket connected (%d device(s))", len(SERVICES))
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Received non-JSON Sinric frame, ignoring: %.100s", raw)
                        continue
                    try:
                        if not _sinric_verify(msg):
                            logger.warning("Ignoring Sinric message with invalid signature")
                            continue
                        payload = msg.get("payload", {})
                        if payload.get("type") != "request":
                            continue
                        action = payload.get("action", "")
                        device_id = payload.get("deviceId", "")
                        value = payload.get("value", {})

                        handler = HANDLERS.get(device_id)
                        if handler is None:
                            logger.warning(
                                "Sinric message for unknown device %r — ignoring", device_id
                            )
                            continue

                        logger.info(
                            "Sinric %s: device=%s type=%s",
                            action, device_id, handler.service_type,
                        )
                        try:
                            result = await handler.handle_action(action, value)
                            success = result.get("success", False)
                            result_value = result.get("value", {})
                        except Exception:
                            logger.exception("Handler %s raised an exception", device_id)
                            success = False
                            result_value = {}

                        resp_payload = {
                            "action": action,
                            "clientId": payload.get("clientId", SINRIC_APP_KEY),
                            "createdAt": int(time.time()),
                            "deviceId": device_id,
                            "message": "OK" if success else "Request failed",
                            "replyToken": payload.get("replyToken", ""),
                            "scope": payload.get("scope", "device"),
                            "success": success,
                            "type": "response",
                            "value": result_value,
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
    if not all([SINRIC_APP_KEY, SINRIC_APP_SECRET]):
        logger.error("Sinric Pro not configured — set SINRIC_APP_KEY and SINRIC_APP_SECRET")
        return
    if not SERVICES:
        logger.warning("No services configured — Sinric Pro loop will connect but route no messages")

    logger.info("Starting Sinric Pro WebSocket client (%d service(s))", len(SERVICES))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_sinric_loop())



# ── FastAPI lifecycle ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify handler configurations now that we're inside an async context
    await _verify_handlers()
    # Start Sinric in a daemon thread so it doesn't block uvicorn
    sinric_thread = Thread(target=_run_sinric, daemon=True, name="sinric-pro")
    sinric_thread.start()
    logger.info("Service started — Sinric Pro WebSocket + local API ready")
    yield
    logger.info("Service shutting down")


app = FastAPI(title="Home Automation Multi-Service", version="3.0.0", lifespan=lifespan)


# ── Local-only endpoints (for manual/debug use from LAN) ────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/services")
def list_services(_net: None = Depends(verify_local_network)):
    """List all registered services (local network only)."""
    return {
        "count": len(SERVICES),
        "services": [
            {"device_id": did, "type": svc["type"], "name": svc["name"]}
            for did, svc in SERVICES.items()
        ],
    }


@app.get("/service/{device_id}/details")
async def service_details(
    device_id: str,
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Return current state/details for any registered service."""
    handler = HANDLERS.get(device_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Service {device_id!r} not found")
    try:
        details = await handler.get_details()
        logger.info("Manual /service/%s/details from %s", device_id, request.client.host)
        return {"device_id": device_id, "type": SERVICES[device_id]["type"], "details": details}
    except Exception:
        logger.exception("Error handling request for device %s", device_id)
        raise HTTPException(status_code=500, detail="Internal error — check service logs")


@app.post("/service/{device_id}/on")
async def service_on(
    device_id: str,
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Turn on a registered service device."""
    handler = HANDLERS.get(device_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Service {device_id!r} not found")
    try:
        result = await handler.handle_action("setPowerState", {"state": "On"})
        if not result.get("success"):
            raise HTTPException(status_code=502, detail=result.get("message", "Operation failed"))
        logger.info("Manual /service/%s/on from %s", device_id, request.client.host)
        return {"action": "on", "device_id": device_id, **result}
    except Exception:
        logger.exception("Error handling request for device %s", device_id)
        raise HTTPException(status_code=500, detail="Internal error — check service logs")


@app.post("/service/{device_id}/off")
async def service_off(
    device_id: str,
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Turn off a registered service device."""
    handler = HANDLERS.get(device_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Service {device_id!r} not found")
    try:
        result = await handler.handle_action("setPowerState", {"state": "Off"})
        if not result.get("success"):
            raise HTTPException(status_code=502, detail=result.get("message", "Operation failed"))
        logger.info("Manual /service/%s/off from %s", device_id, request.client.host)
        return {"action": "off", "device_id": device_id, **result}
    except Exception:
        logger.exception("Error handling request for device %s", device_id)
        raise HTTPException(status_code=500, detail="Internal error — check service logs")


@app.post("/service/{device_id}/toggle")
async def service_toggle(
    device_id: str,
    request: Request,
    _net: None = Depends(verify_local_network),
    _key: str = Depends(verify_token),
):
    """Toggle a registered service device (auto-detect current state)."""
    handler = HANDLERS.get(device_id)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Service {device_id!r} not found")
    try:
        current = await handler.get_state()
        new_state = "Off" if current else "On"
        result = await handler.handle_action("setPowerState", {"state": new_state})
        if not result.get("success"):
            raise HTTPException(status_code=502, detail=result.get("message", "Operation failed"))
        logger.info(
            "Manual /service/%s/toggle from %s: %s→%s",
            device_id, request.client.host, current, new_state,
        )
        return {"action": "toggle", "device_id": device_id, "was": current, "now": new_state == "On", **result}
    except Exception:
        logger.exception("Error handling request for device %s", device_id)
        raise HTTPException(status_code=500, detail="Internal error — check service logs")
