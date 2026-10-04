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
BASE_URL = "https://flashtopup.com/api/reseller/v2"
SIGN_PATH_PREFIX = "/api/reseller/v2"

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        )
    return _session


async def close():
    """অ্যাপ বন্ধ করার সময় কল করুন।"""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None


def _sign(method: str, path: str, body: str = "",
          sandbox: bool = False) -> dict:
    """Generate HMAC-SHA256 signed headers."""
    api_id  = os.getenv("FLASHTOPUP_API_ID", "")
    api_key = os.getenv("FLASHTOPUP_API_KEY", "")
    if not api_id or not api_key:
        raise RuntimeError(
            "FLASHTOPUP_API_ID / FLASHTOPUP_API_KEY সেট করা নেই"
        )

    timestamp = str(int(time.time()))
    nonce     = str(uuid.uuid4())
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    canonical = "\n".join([method, path, timestamp, nonce, body_hash])
    signature = hmac.new(
        api_key.encode(),
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "X-FT-API-ID":    api_id,
        "X-FT-Timestamp": timestamp,
        "X-FT-Nonce":     nonce,
        "X-FT-Signature": signature,
    }
    if sandbox:
        headers["X-FT-Sandbox"] = "true"
    return headers


async def _request(method: str, endpoint: str, *,
                   params: dict | None = None,
                   json_body: dict | None = None,
                   sandbox: bool = False) -> dict:
    """Low-level রিকোয়েস্ট — সব public ফাংশন এটাকে কল করে।"""
    sign_path = f"{SIGN_PATH_PREFIX}{endpoint}"
    body = json.dumps(json_body, separators=(",", ":")) if json_body else ""
    headers = _sign(method, sign_path, body, sandbox=sandbox)
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    url     = BASE_URL + endpoint
    session = await _get_session()

    try:
        async with session.request(
            method, url, headers=headers, params=params,
            data=body if json_body is not None else None,
        ) as resp:
            request_id = resp.headers.get("X-FT-Request-ID")
            try:
                payload = await resp.json(content_type=None)
            except Exception:
                text = await resp.text()
                logger.error("FlashTopup %s %s invalid JSON: %s",
                             method, endpoint, text[:300])
                return {
                    "success": False, "data": None,
                    "error": {"code": "INVALID_JSON",
                              "message": text[:200] or "Empty response"},
                    "meta": {"request_id": request_id},
                }
            if payload is None:
                return {
                    "success": False, "data": None,
                    "error": {"code": "EMPTY_RESPONSE",
                              "message": "Empty response"},
                    "meta": {"request_id": request_id},
                }
            return payload
    except aiohttp.ClientError as e:
        logger.error("FlashTopup %s %s network error: %s", method, endpoint, e)
        return {
            "success": False, "data": None,
            "error": {"code": "NETWORK_ERROR", "message": str(e)},
            "meta": {},
        }
    except Exception as e:
        logger.exception("FlashTopup %s %s unexpected error", method, endpoint)
        return {
            "success": False, "data": None,
            "error": {"code": "UNEXPECTED_ERROR", "message": str(e)},
            "meta": {},
        }


# ── Public API ────────────────────────────────────────────────────

async def get_profile() -> dict:
    """Auth check + currency info."""
    return await _request("GET", "/profile")


async def get_balance() -> dict:
    """Get reseller wallet balance."""
    return await _request("GET", "/balance")


async def get_products(page: int = 1, per_page: int = 500,
                       cursor: str | None = None) -> dict:
    """Get all game/product list."""
    params: dict = {"page": page, "per_page": per_page}
    if cursor:
        params["cursor"] = cursor
    return await _request("GET", "/products", params=params)


async def get_services(product_code: str, product_type: str,
                       page: int = 1, per_page: int = 500,
                       cursor: str | None = None) -> dict:
    """
    Get package list for a product.
    v2: product_code (stable) ব্যবহার করতে হবে, product_id নয়।
    """
    params: dict = {
        "product_code": product_code,
        "product_type": product_type,
        "page":         page,
        "per_page":     per_page,
    }
    if cursor:
        params["cursor"] = cursor
    return await _request("GET", "/services", params=params)


async def check_player_id(user_id: str, validation_code: str,
                          server_id: str | None = None,
                          sandbox: bool = False) -> dict:
    """
    /check-id — শুধু ফিক্সড ফিল্ড: user_id, validation_code,
    ঐচ্ছিক server_id।
    """
    body: dict = {
        "user_id":         user_id,
        "validation_code": validation_code,
    }
    if server_id is not None and str(server_id) != "":
        body["server_id"] = server_id
    return await _request("POST", "/check-id",
                          json_body=body, sandbox=sandbox)


async def place_order(service_code: str, reference_id: str,
                      account_fields: dict,
                      quantity: int = 1,
                      sandbox: bool = False) -> dict:
    """
    /order — dynamic order fields। account_fields-এ Products API
    `fields[]` থেকে আসা নামগুলো হুবহু বসান (user_id, server_id,
    target_id, zone_id ইত্যাদি)।
    """
    body: dict = {
        "service_code": service_code,
        "reference_id": reference_id,
        "quantity":     quantity,
    }
    for k, v in (account_fields or {}).items():
        if v is not None:
            body[k] = v
    return await _request("POST", "/order",
                          json_body=body, sandbox=sandbox)


async def get_order_status(order_id: str | None = None,
                           reference_id: str | None = None) -> dict:
    """Get status of a single order."""
    if not order_id and not reference_id:
        raise ValueError("order_id অথবা reference_id দিতে হবে")
    params: dict = {}
    if order_id:
        params["order_id"] = order_id
    if reference_id:
        params["reference_id"] = reference_id
    return await _request("GET", "/order/status", params=params)


async def bulk_order_status(order_ids: list[str] | None = None,
                            reference_ids: list[str] | None = None) -> dict:
    """Check up to 50 orders in one request."""
    if not order_ids and not reference_ids:
        raise ValueError("order_ids অথবা reference_ids দিতে হবে")
    if (len(order_ids or []) + len(reference_ids or [])) > 50:
        raise ValueError("সর্বোচ্চ ৫০টি আইডি প্রতি রিকোয়েস্টে")
    body: dict = {}
    if order_ids:
        body["order_ids"] = order_ids
    if reference_ids:
        body["reference_ids"] = reference_ids
    return await _request("POST", "/orders/status", json_body=body)


def make_reference_id(prefix: str = "ORD") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"