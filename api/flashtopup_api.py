"""
FlashTopup Reseller API v2 — HMAC-SHA256 authenticated wrapper
"""
import hashlib
import hmac
import json
import os
import time
import uuid
import logging
import aiohttp

logger   = logging.getLogger(__name__)
BASE_URL = "https://api.flashtopup.com/api/reseller/v2"


def _sign(method: str, path: str, body: str = "") -> dict:
    """Generate HMAC-SHA256 signed headers."""
    api_id    = os.getenv("FLASHTOPUP_API_ID", "")
    api_key   = os.getenv("FLASHTOPUP_API_KEY", "")
    timestamp = str(int(time.time()))
    nonce     = str(uuid.uuid4())
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    canonical = "\n".join([method, path, timestamp, nonce, body_hash])
    signature = hmac.new(
        api_key.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()
    api_id_val = api_id
    return {
        "Content-Type":   "application/json",
        "X-FT-API-ID":    api_id_val,
        "X-FT-Timestamp": timestamp,
        "X-FT-Nonce":     nonce,
        "X-FT-Signature": signature,
    }


async def _get(endpoint: str, params: dict = None) -> dict:
    path = f"/api/reseller/v2{endpoint}"
    headers = _sign("GET", path)
    url = BASE_URL + endpoint
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)
                return data if data is not None else {"error": "Empty response"}
    except Exception as e:
        logger.error(f"FlashTopup GET {endpoint} error: {e}")
        return {"error": str(e), "success": False}


async def _post(endpoint: str, data: dict) -> dict:
    path = f"/api/reseller/v2{endpoint}"
    body = json.dumps(data, separators=(",", ":"))
    headers = _sign("POST", path, body)
    url = BASE_URL + endpoint
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=body, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)
                return data if data is not None else {"error": "Empty response"}
    except Exception as e:
        logger.error(f"FlashTopup POST {endpoint} error: {e}")
        return {"error": str(e), "success": False}


# ── Public API ────────────────────────────────────────────────────

async def get_balance() -> dict:
    """Get reseller wallet balance."""
    return await _get("/balance")


async def get_products(page: int = 1, per_page: int = 500) -> dict:
    """Get all game/product list."""
    return await _get("/products", {"page": page, "per_page": per_page})


async def get_services(product_code: str, product_type: str) -> dict:
    """Get package list for a specific product."""
    return await _get("/services", {
        "product_code": product_code,
        "product_type": product_type
    })


async def check_player_id(user_id: str, server_id: str, validation_code: str) -> dict:
    """Validate a player ID before ordering."""
    return await _post("/check-id", {
        "user_id":         user_id,
        "server_id":       server_id,
        "validation_code": validation_code,
    })


async def place_order(service_code: str, user_id: str, server_id: str,
                      reference_id: str, quantity: int = 1) -> dict:
    """Place a topup order."""
    return await _post("/order", {
        "service_code": service_code,
        "reference_id": reference_id,
        "quantity":     quantity,
        "user_id":      user_id,
        "server_id":    server_id,
    })


async def get_order_status(order_id: str = None, reference_id: str = None) -> dict:
    """Get status of a single order."""
    params = {}
    if order_id:
        params["order_id"] = order_id
    if reference_id:
        params["reference_id"] = reference_id
    return await _get("/order/status", params)
