import os
import httpx
import logging
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class HomeboxClient:
    def __init__(self):
        load_dotenv()
        self.local_url = os.getenv("HOMEBOX_LOCAL_URL", "http://10.0.0.4:7745").rstrip("/")
        self.wan_url = os.getenv("HOMEBOX_WAN_URL", "").rstrip("/")
        self.use_lan_api = os.getenv("USE_LAN_API", "true").lower() != "false"
        self._load_env_credentials()
        self.client = httpx.AsyncClient(timeout=30.0)

    def _load_env_credentials(self):
        """Loads credentials from environment variables."""
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.username, self.password = os.getenv("HOMEBOX_USERNAME"), os.getenv("HOMEBOX_PASSWORD")
        self.token, self.token_expiry = self.api_key, None
        if self.api_key: self.token_expiry = datetime.now(timezone.utc) + timedelta(days=365*10)

    async def login_manual(self, username, password):
        """Manually log in as a different user."""
        self.username, self.password, self.api_key = username, password, None
        await self.login()

    def logout(self):
        """Logout and revert to environment credentials."""
        self._load_env_credentials()

    @property
    def api_base_url(self) -> str:
        base = self.local_url if self.use_lan_api else (self.wan_url or self.local_url)
        return f"{base}/api/v1"

    def get_web_url(self, resource_type: str, id: str) -> str:
        base = self.local_url if os.getenv("LAN_LINKS", "false").lower() == "true" or not self.wan_url else self.wan_url
        return f"{base}/{resource_type}/{id}"

    async def login(self):
        if self.api_key: return
        if not self.username or not self.password: raise ValueError("Authentication requires HOMEBOX_API_KEY or HOMEBOX_USERNAME and HOMEBOX_PASSWORD")
        try:
            response = await self.client.post(f"{self.api_base_url}/users/login", json={"username": self.username, "password": self.password})
            response.raise_for_status()
            data = response.json()
            self.token = data["token"].replace("Bearer ", "", 1) if data.get("token") else None
            self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00")) if "expiresAt" in data else datetime.now(timezone.utc) + timedelta(hours=24)
            logger.info(f"Logged in successfully. Token expires: {self.token_expiry}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    async def refresh_token(self):
        if self.api_key: return
        try:
            response = await self.client.get(f"{self.api_base_url}/users/refresh", headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            data = response.json()
            if "token" in data: self.token = data["token"].replace("Bearer ", "", 1)
            self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00")) if "expiresAt" in data else datetime.now(timezone.utc) + timedelta(hours=24)
            logger.info("Token refreshed")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}"); await self.login()

    async def ensure_valid_token(self):
        if self.api_key: return
        if not self.token or not self.token_expiry or datetime.now(timezone.utc) + timedelta(minutes=5) > self.token_expiry: await self.login() if not self.token else await self.refresh_token()

    async def request(self, method: str, endpoint: str, return_bytes: bool = False, **kwargs) -> Any:
        await self.ensure_valid_token()
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {}); headers["Authorization"] = f"Bearer {self.token}"
        if "json" in kwargs: logger.info(f"API Request Body: {json.dumps(kwargs['json'])}")
        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            if response.status_code >= 400: logger.error(f"API Error Response Body: {response.text}")
            response.raise_for_status()
            if response.status_code == 204: return None
            if return_bytes: return response.content
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try: return response.json()
                except json.JSONDecodeError: logger.warning(f"Failed to decode JSON from {url}, returning text instead."); return response.text
            elif "image/" in content_type: return f"data:{content_type};base64,{base64.b64encode(response.content).decode('utf-8')}"
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error {e.response.status_code} for {method} {url}: {e.response.text}"); raise
        except Exception as e:
            logger.error(f"Request failed: {e}"); raise

    async def close(self): await self.client.aclose()