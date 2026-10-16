import aiohttp
import logging
from config import CSB_API_URL, CSB_API_KEY

logger = logging.getLogger(__name__)


class CSBApiClient:
    def __init__(self, api_url: str = CSB_API_URL, api_key: str = CSB_API_KEY):
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

    async def _post(self, **params) -> dict | list:
        session = await self._get_session()
        data = {"key": self.api_key, **params}
        try:
            async with session.post(self.api_url, data=data) as resp:
                result = await resp.json(content_type=None)
                return result
        except aiohttp.ClientError as e:
            logger.error(f"CSB API request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"CSB API unexpected error: {e}")
            return {"error": str(e)}

    # ── Services ──────────────────────────────────────────────────
    async def get_services(self) -> list[dict]:
        result = await self._post(action="services")
        if isinstance(result, list):
            return result
        return []

    # ── Add Order ─────────────────────────────────────────────────
    async def add_order(self, service: str, link: str, quantity: int) -> dict:
        result = await self._post(
            action="add",
            service=service,
            link=link,
            quantity=quantity,
        )
        if isinstance(result, dict):
            return result
        return {"error": "Unexpected response"}

    # ── Order Status ─────────────────────────────────────────────
    async def order_status(self, order_id: str) -> dict:
        result = await self._post(action="status", order=order_id)
        if isinstance(result, dict):
            return result
        return {"error": "Unexpected response"}

    # ── Balance ───────────────────────────────────────────────────
    async def get_balance(self) -> dict:
        result = await self._post(action="balance")
        if isinstance(result, dict):
            return result
        return {"error": "Unexpected response"}

    # ── Test Connection ───────────────────────────────────────────
    async def test_connection(self) -> tuple[bool, str]:
        result = await self.get_balance()
        if "error" in result:
            return False, result["error"]
        if "balance" in result:
            bal   = result["balance"]
            curr  = result.get("currency", "CSBPOINT")
            return True, f"Balance: {bal} {curr}"
        return False, "Unknown response"


# Singleton
csb_api = CSBApiClient()
