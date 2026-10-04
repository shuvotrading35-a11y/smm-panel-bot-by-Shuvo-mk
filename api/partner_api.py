"""
Partner API v1 client — https://ggsoma.store/api/partner/v1

সব HTTP কল এখান থেকেই হবে। হ্যান্ডলারে সরাসরি aiohttp/requests নয়।

⚠️ সব public function async — হ্যান্ডলারে অবশ্যই await করতে হবে।
"""
import asyncio
import logging
import aiohttp

from config import PARTNER_API_BASE, PARTNER_API_KEY

log = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None


# ─────────────────────────────────────────────────────
#  ERROR
# ─────────────────────────────────────────────────────
class PartnerAPIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        request_id: str | None = None,
        extra: dict | None = None,
    ):
        self.code       = code
        self.message    = message
        self.request_id = request_id
        self.extra      = extra or {}
        super().__init__(f"{code}: {message}")


# ─────────────────────────────────────────────────────
#  SESSION
# ─────────────────────────────────────────────────────
async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "Authorization": f"Bearer {PARTNER_API_KEY}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
        )
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


# ─────────────────────────────────────────────────────
#  CORE REQUEST
# ─────────────────────────────────────────────────────
async def _request(method: str, path: str, json_body: dict | None = None) -> dict:
    if not PARTNER_API_KEY:
        raise PartnerAPIError("NO_KEY", "PARTNER_API_KEY সেট করা নেই (.env চেক করুন)")

    url = f"{PARTNER_API_BASE}{path}"
    session = await get_session()

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            async with session.request(method, url, json=json_body) as resp:
                # রেট লিমিট বা সার্ভার এরর → ব্যাকঅফ
                if resp.status == 429 or resp.status >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue

                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    raise PartnerAPIError(
                        "BAD_JSON",
                        f"HTTP {resp.status}: {text[:200]}",
                    )

        except aiohttp.ClientError as e:
            last_err = e
            await asyncio.sleep(2 ** attempt)
            continue

        # API-লেভেল এরর
        if isinstance(data, dict) and data.get("ok") is False:
            err = data.get("error", {}) or {}
            raise PartnerAPIError(
                err.get("code", "UNKNOWN"),
                err.get("message", "Unknown error"),
                err.get("requestId"),
                {k: v for k, v in err.items()
                 if k not in ("code", "message", "requestId")},
            )
        return data

    raise PartnerAPIError("NETWORK", f"রিট্রাই শেষেও ফেল: {last_err}")


# ─────────────────────────────────────────────────────
#  PUBLIC API  (সব async)
# ─────────────────────────────────────────────────────
async def health() -> dict:
    """GET /health — সার্ভিস স্ট্যাটাস।"""
    return await _request("GET", "/health")


async def balance() -> dict:
    """GET /balance — USD ব্যালেন্স।"""
    return await _request("GET", "/balance")


async def providers() -> list[dict]:
    """GET /catalog/providers — ক্যাটাগরি লিস্ট।"""
    data = await _request("GET", "/catalog/providers")
    return data.get("data", [])


async def products(provider: str | None = None) -> list[dict]:
    """GET /catalog/products[?provider=X] — প্রোডাক্ট লিস্ট।"""
    path = "/catalog/products"
    if provider:
        path += f"?provider={provider}"
    data = await _request("GET", path)
    return data.get("data", [])


async def product(ref: str) -> dict:
    """GET /catalog/products/:ref — একটি প্রোডাক্ট ডিটেইল।"""
    return await _request("GET", f"/catalog/products/{ref}")


async def create_order(
    product_slug: str,
    quantity: int,
    external_order_id: str,
) -> dict:
    """POST /orders — নতুন অর্ডার।"""
    return await _request("POST", "/orders", {
        "productSlug":     product_slug,
        "quantity":        quantity,
        "externalOrderId": external_order_id,
    })


async def get_order(order_code: str) -> dict:
    """GET /orders/:orderCode — অর্ডার ডিটেইল + ডেলিভারি।"""
    return await _request("GET", f"/orders/{order_code}")


async def list_orders(page: int = 1, limit: int = 20) -> dict:
    """GET /orders — API অর্ডার লিস্ট (পেজিনেটেড)।"""
    return await _request("GET", f"/orders?page={page}&limit={limit}")


async def usage() -> dict:
    """GET /usage — অ্যাকাউন্ট ইউজেজ স্ট্যাট।"""
    return await _request("GET", "/usage")