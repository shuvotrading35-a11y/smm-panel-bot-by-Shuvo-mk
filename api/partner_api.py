"""
Partner API v1 client — https://ggsoma.store/api/partner/v1
সব কল এখান থেকেই হবে। কোনো হ্যান্ডলার সরাসরি requests করবে না।
"""
import time
import logging
import requests
from config import PARTNER_API_BASE, PARTNER_API_KEY

log = logging.getLogger(__name__)


class PartnerAPIError(Exception):
    def __init__(self, code, message, request_id=None, extra=None):
        self.code = code
        self.message = message
        self.request_id = request_id
        self.extra = extra or {}
        super().__init__(f"{code}: {message}")


def _headers():
    return {
        "Authorization": f"Bearer {PARTNER_API_KEY}",
        "Content-Type": "application/json",
    }


def _request(method, path, **kw):
    if not PARTNER_API_KEY:
        raise PartnerAPIError("NO_KEY", "PARTNER_API_KEY সেট করা নেই")

    url = f"{PARTNER_API_BASE}{path}"
    last_err = None

    for attempt in range(4):
        try:
            r = requests.request(method, url, headers=_headers(), timeout=25, **kw)
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
            continue

        # রেট লিমিট বা সার্ভার এরর → ব্যাকঅফ করে রিট্রাই
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue

        try:
            data = r.json()
        except ValueError:
            raise PartnerAPIError("BAD_JSON", f"HTTP {r.status_code}: {r.text[:200]}")

        if data.get("ok") is False:
            err = data.get("error", {})
            raise PartnerAPIError(
                err.get("code", "UNKNOWN"),
                err.get("message", "Unknown error"),
                err.get("requestId"),
                {k: v for k, v in err.items() if k not in ("code", "message", "requestId")},
            )
        return data

    raise PartnerAPIError("NETWORK", f"রিট্রাই শেষেও ফেল: {last_err}")


# ── Public functions ────────────────────────────────────────────────────────

def health():
    return _request("GET", "/health")


def balance():
    return _request("GET", "/balance")


def providers():
    return _request("GET", "/catalog/providers").get("data", [])


def products(provider: str | None = None):
    path = "/catalog/products" + (f"?provider={provider}" if provider else "")
    return _request("GET", path).get("data", [])


def product(ref: str):
    return _request("GET", f"/catalog/products/{ref}")


def create_order(product_slug: str, quantity: int, external_order_id: str):
    return _request("POST", "/orders", json={
        "productSlug": product_slug,
        "quantity": quantity,
        "externalOrderId": external_order_id,
    })


def get_order(order_code: str):
    return _request("GET", f"/orders/{order_code}")


def list_orders(page: int = 1, limit: int = 20, external_order_id: str | None = None):
    q = f"?page={page}&limit={limit}"
    if external_order_id:
        q += f"&externalOrderId={external_order_id}"
    return _request("GET", f"/orders{q}")


def usage():
    return _request("GET", "/usage")


# ── Shutdown hook (called from bot.py) ──────────────────────────────────────

def close_session():
    """
    Shutdown hook for the partner API client.

    Current implementation uses `requests.request()` directly (no
    persistent Session object), so there is nothing to close.
    This function exists so bot.py's shutdown handler works correctly.

    If you later switch to a persistent `requests.Session()` or
    `httpx.AsyncClient`, close it here.
    """
    log.info("Partner API client closed (no-op — using requests per-call).")
    return None