"""
Verification script to test that all core package imports are functional.
Run this to verify extraction was successful before proceeding to Phase 2.5.6.

Usage:
    python verify_core_imports.py
"""

import sys
from pathlib import Path

# Add python-service to path so we can import core
python_service_path = Path(__file__).parent / "python-service"
sys.path.insert(0, str(python_service_path))

print("=" * 70)
print("CORE PACKAGE IMPORT VERIFICATION")
print("=" * 70)

# Test utils imports
print("\n✓ Testing core.utils imports...")
try:
    from core.utils import (
        get_logger,
        parse_allowed_networks,
        is_allowed_ip,
        HTTPClient,
        create_insecure_ssl_context,
        HMACHelper,
        normalize_response,
        run_async_in_thread,
    )
    print("  ✅ All 8 utils imported successfully")
except ImportError as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)

# Test auth imports
print("\n✓ Testing core.auth imports...")
try:
    from core.auth import verify_token, verify_local_network
    print("  ✅ All 2 auth utilities imported successfully")
except ImportError as e:
    if "fastapi" in str(e).lower():
        print(f"  ⚠️  Skipped (FastAPI not installed): {e}")
    else:
        print(f"  ❌ Import error: {e}")
        sys.exit(1)

# Test websocket imports
print("\n✓ Testing core.websocket imports...")
try:
    from core.websocket import AutoReconnectingWebSocket
    print("  ✅ WebSocket utilities imported successfully")
except ImportError as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)

# Test fastapi_helpers imports
print("\n✓ Testing core.fastapi_helpers imports...")
try:
    from core.fastapi_helpers import create_lifespan, lifespan_with_callback
    print("  ✅ FastAPI helpers imported successfully")
except ImportError as e:
    if "fastapi" in str(e).lower():
        print(f"  ⚠️  Skipped (FastAPI not installed): {e}")
    else:
        print(f"  ❌ Import error: {e}")
        sys.exit(1)

# Quick functionality tests
print("\n" + "=" * 70)
print("QUICK FUNCTIONALITY TESTS")
print("=" * 70)

print("\n✓ Testing get_logger()...")
try:
    logger = get_logger("test_logger")
    assert logger is not None
    print("  ✅ get_logger() works")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing parse_allowed_networks()...")
try:
    networks = parse_allowed_networks("127.0.0.1,192.168.0.0/16,10.0.0.0/8")
    assert len(networks) == 3
    print(f"  ✅ parse_allowed_networks() works — parsed {len(networks)} networks")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing is_allowed_ip()...")
try:
    networks = parse_allowed_networks("127.0.0.1,192.168.0.0/16")
    allowed = is_allowed_ip("127.0.0.1", networks)
    not_allowed = is_allowed_ip("8.8.8.8", networks)
    assert allowed and not not_allowed
    print("  ✅ is_allowed_ip() works correctly")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing HMACHelper()...")
try:
    helper = HMACHelper("secret-key")
    payload = {"action": "test", "value": 123}
    signature = helper.sign(payload)
    assert len(signature) > 0
    assert helper.verify({
        "payload": payload,
        "signature": {"HMAC": signature}
    })
    print("  ✅ HMACHelper works (sign/verify)")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing normalize_response()...")
try:
    data = {"id": "123", "name": "test", "enabled": True, "meta": "ignore"}
    normalized = normalize_response(data, {"id", "meta"})
    assert "id" not in normalized
    assert "meta" not in normalized
    assert "name" in normalized
    print("  ✅ normalize_response() works")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing create_insecure_ssl_context()...")
try:
    ctx = create_insecure_ssl_context()
    import ssl
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    print("  ✅ create_insecure_ssl_context() works")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n✓ Testing HTTPClient initialization...")
try:
    client = HTTPClient(headers={"X-API-Key": "test"})
    assert client.headers == {"X-API-Key": "test"}
    print("  ✅ HTTPClient initializes correctly")
except Exception as e:
    print(f"  ❌ Error: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL VERIFICATION TESTS PASSED")
print("=" * 70)
print("\nCore package is ready for use in Phase 2.5.6 refactoring.")
print("Import structure:")
print("  - from core.utils import ...")
print("  - from core.auth import ...")
print("  - from core.websocket import ...")
print("  - from core.fastapi_helpers import ...")
