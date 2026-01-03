import os
import httpx
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class HomeboxClient:
    def __init__(self):
        load_dotenv()
        self.local_url = os.getenv("HOMEBOX_LOCAL_URL", "http://10.0.0.4:7745").rstrip("/")
        self.wan_url = os.getenv("HOMEBOX_WAN_URL", "").rstrip("/")
        self.use_lan_api = os.getenv("USE_LAN_API", "true").lower() != "false"
        
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.username = os.getenv("HOMEBOX_USERNAME")
        self.password = os.getenv("HOMEBOX_PASSWORD")
        
        self.token: Optional[str] = self.api_key
        self.token_expiry: Optional[datetime] = None
        
        self._load_env_credentials()

        self.client = httpx.AsyncClient(timeout=30.0)

    def _load_env_credentials(self):
        """Loads credentials from environment variables."""
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.username = os.getenv("HOMEBOX_USERNAME")
        self.password = os.getenv("HOMEBOX_PASSWORD")
        
        self.token = self.api_key
        self.token_expiry = None
        
        # If using API key, set expiry to far future
        if self.api_key:
            self.token_expiry = datetime.now(timezone.utc) + timedelta(days=365*10)

    async def login_manual(self, username, password):
        """Manually log in as a different user."""
        self.username = username
        self.password = password
        self.api_key = None  # Disable API key mode to force Bearer token usage
        await self.login()

    def logout(self):
        """Logout and revert to environment credentials."""
        self._load_env_credentials()


    @property
    def api_base_url(self) -> str:
        base = self.local_url if self.use_lan_api else (self.wan_url or self.local_url)
        return f"{base}/api/v1"

    def get_web_url(self, resource_type: str, id: str) -> str:
        lan_links = os.getenv("LAN_LINKS", "false").lower() == "true"
        base = self.local_url
        if not lan_links and self.wan_url:
            base = self.wan_url
        return f"{base}/{resource_type}/{id}"

    async def login(self):
        if self.api_key:
            return
        if not self.username or not self.password:
            raise ValueError("Authentication requires HOMEBOX_API_KEY or HOMEBOX_USERNAME and HOMEBOX_PASSWORD")
        url = f"{self.api_base_url}/users/login"
        try:
            response = await self.client.post(url, json={
                "username": self.username,
                "password": self.password
            })
            response.raise_for_status()
            data = response.json()
            self.token = data["token"].replace("Bearer ", "", 1) if data.get("token") else None
            if "expiresAt" in data:
                 self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            else:
                 self.token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
            logger.info(f"Logged in successfully. Token expires: {self.token_expiry}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    async def refresh_token(self):
        if self.api_key:
            return
        url = f"{self.api_base_url}/users/refresh"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if "token" in data:
                self.token = data["token"].replace("Bearer ", "", 1)
            if "expiresAt" in data:
                self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            else:
                self.token_expiry = datetime.now(timezone.utc) + timedelta(hours=24)
            logger.info("Token refreshed")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            await self.login()

    async def ensure_valid_token(self):
        if self.api_key:
            return
        if not self.token or not self.token_expiry:
            await self.login()
            return
        if datetime.now(timezone.utc) + timedelta(minutes=5) > self.token_expiry:
            await self.refresh_token()

    async def request(self, method: str, endpoint: str, **kwargs) -> Any:
        await self.ensure_valid_token()
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        
        # Log request body for debugging 500s
        if "json" in kwargs:
            logger.info(f"API Request Body: {json.dumps(kwargs['json'])}")
        
        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            
            if response.status_code >= 400:
                logger.error(f"API Error Response Body: {response.text}")
                
            response.raise_for_status()
            if response.status_code == 204:
                return None
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode JSON from {url}, returning text instead.")
                    return response.text
            elif "image/" in content_type:
                return response.content
            else:
                return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"API Error {e.response.status_code} for {method} {url}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    async def close(self):
        await self.client.aclose()
