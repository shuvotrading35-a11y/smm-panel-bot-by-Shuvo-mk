import aiohttp
import asyncio
from config import SMM_API_URL, SMM_API_KEY
import logging

logger = logging.getLogger(__name__)


class SMMApiClient:
    def __init__(self, api_url: str = SMM_API_URL, api_key: str = SMM_API_KEY):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _post(self, **params) -> dict:
        session = await self._get_session()
        data = {"key": self.api_key, **params}
        try:
            async with session.post(self.api_url, data=data) as resp:
                result = await resp.json(content_type=None)
                return result
        except aiohttp.ClientError as e:
            logger.error(f"SMM API request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"SMM API unexpected error: {e}")
            return {"error": str(e)}

    # ── Services ──────────────────────────────────────────────────
    async def get_services(self) -> list[dict]:
        result = await self._post(action="services")
        if isinstance(result, list):
            return result
        return []

    # ── Add Order ─────────────────────────────────────────────────
    async def add_order(self, service: str, link: str, quantity: int) -> dict:
        return await self._post(
            action="add",
            service=service,
            link=link,
            quantity=quantity,
        )

    # ── Order Status ─────────────────────────────────────────────
    async def order_status(self, order_id: str) -> dict:
        return await self._post(action="status", order=order_id)

    # ── Multiple Order Status ─────────────────────────────────────
    async def multiple_status(self, order_ids: list[str]) -> dict:
        ids = ",".join(order_ids)
        return await self._post(action="status", orders=ids)

    # ── Refill (Single) ───────────────────────────────────────────
    async def refill_order(self, order_id: str) -> dict:
        return await self._post(action="refill", order=order_id)

    # ── Refill (Multiple) ─────────────────────────────────────────
    async def refill_multiple_orders(self, order_ids: list[str]) -> list:
        ids = ",".join(order_ids)
        result = await self._post(action="refill", orders=ids)
        if isinstance(result, list):
            return result
        return [{"error": str(result)}]

    # ── Refill Status (Single) ────────────────────────────────────
    async def refill_status(self, refill_id: str) -> dict:
        return await self._post(action="refill_status", refill=refill_id)

    # ── Refill Status (Multiple) ──────────────────────────────────
    async def refill_status_multiple(self, refill_ids: list[str]) -> list:
        ids = ",".join(refill_ids)
        result = await self._post(action="refill_status", refills=ids)
        if isinstance(result, list):
            return result
        return [{"error": str(result)}]

    # ── Cancel ────────────────────────────────────────────────────
    async def cancel_order(self, order_id: str) -> dict:
        return await self._post(action="cancel", orders=order_id)

    # ── Balance ───────────────────────────────────────────────────
    async def get_balance(self) -> dict:
        return await self._post(action="balance")

    # ── Helpers ───────────────────────────────────────────────────
    async def test_connection(self) -> tuple[bool, str]:
        result = await self.get_balance()
        if "error" in result:
            return False, result["error"]
        if "balance" in result:
            usd = float(result['balance'])
            bdt = usd * 135  # 1 USD ≈ 110 BDT
            return True, f"Balance: ${usd:.4f} USD (≈ ৳{bdt:.2f} BDT)"
        return False, "Unknown response"


# Singleton
smm_api = SMMApiClient()