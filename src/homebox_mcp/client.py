import base64
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class HomeboxClient:
    """
    Client for interacting with the Homebox API.
    Handles authentication, token management, and request routing.
    """

    def __init__(self):
        load_dotenv()
        self.local_url = os.getenv("HOMEBOX_LOCAL_URL", "http://10.0.0.4:7745").rstrip("/")
        self.wan_url = os.getenv("HOMEBOX_WAN_URL", "").rstrip("/")
        self.use_lan_api = os.getenv("USE_LAN_API", "true").lower() != "false"

        # Load credentials
        self._load_env_credentials()

        # Async HTTP client
        self.client = httpx.AsyncClient(timeout=30.0)

    def _load_env_credentials(self):
        """Loads credentials from environment variables."""
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.username = os.getenv("HOMEBOX_USERNAME")
        self.password = os.getenv("HOMEBOX_PASSWORD")

        self.token = self.api_key
        self.token_expiry = None

        # If using API key, set expiry to far future to avoid unnecessary logins
        if self.api_key:
            self.token_expiry = datetime.now(UTC) + timedelta(days=365 * 10)

    async def login_manual(self, username, password):
        """
        Manually log in as a different user.
        Disables API key mode to force Bearer token usage.
        """
        self.username = username
        self.password = password
        self.api_key = None
        await self.login()

    def logout(self):
        """Logout and revert to default environment credentials."""
        self._load_env_credentials()

    @property
    def api_base_url(self) -> str:
        """Determines the correct API base URL based on network configuration."""
        base = self.local_url if self.use_lan_api else (self.wan_url or self.local_url)
        return f"{base}/api/v1"

    def get_web_url(self, resource_type: str, id: str) -> str:
        """Constructs a direct web interface link for a resource."""
        # Use LAN links if requested or if WAN is unavailable
        use_lan = os.getenv("LAN_LINKS", "false").lower() == "true"
        base = self.local_url if (use_lan or not self.wan_url) else self.wan_url
        return f"{base}/{resource_type}/{id}"

    async def login(self):
        """Authenticates with the Homebox backend using username/password."""
        if self.api_key:
            return

        if not self.username or not self.password:
            raise ValueError("Authentication requires HOMEBOX_API_KEY or HOMEBOX_USERNAME and HOMEBOX_PASSWORD")

        try:
            url = f"{self.api_base_url}/users/login"
            payload = {"username": self.username, "password": self.password}

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            # Remove Bearer prefix if backend includes it
            self.token = data["token"].replace("Bearer ", "", 1) if data.get("token") else None

            # Parse expiry
            if "expiresAt" in data:
                self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            else:
                self.token_expiry = datetime.now(UTC) + timedelta(hours=24)

            logger.info(f"Logged in successfully. Token expires: {self.token_expiry}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    async def refresh_token(self):
        """Refreshes the current JWT token."""
        if self.api_key:
            return

        try:
            url = f"{self.api_base_url}/users/refresh"
            headers = {"Authorization": f"Bearer {self.token}"}

            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            if "token" in data:
                self.token = data["token"].replace("Bearer ", "", 1)

            if "expiresAt" in data:
                self.token_expiry = datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00"))
            else:
                self.token_expiry = datetime.now(UTC) + timedelta(hours=24)

            logger.info("Token refreshed")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            # Try to log in from scratch if refresh fails
            await self.login()

    async def ensure_valid_token(self):
        """Checks token validity and performs login/refresh if necessary."""
        if self.api_key:
            return

        now = datetime.now(UTC)
        # Refresh if token is missing, expired, or expiring within 5 minutes
        if not self.token or not self.token_expiry or (now + timedelta(minutes=5) > self.token_expiry):
            if not self.token:
                await self.login()
            else:
                await self.refresh_token()

    async def request(self, method: str, endpoint: str, return_bytes: bool = False, **kwargs) -> Any:
        """
        Sends an authenticated request to the Homebox API.
        Handles JSON decoding, binary data, and error reporting.
        """
        await self.ensure_valid_token()

        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"

        # Prepare headers
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        # Debug logging for complex request payloads
        if "json" in kwargs:
            logger.info(f"API Request Body: {json.dumps(kwargs['json'])}")

        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)

            # Log error bodies for 4xx/5xx responses
            if response.status_code >= 400:
                logger.error(f"API Error Response Body: {response.text}")

            response.raise_for_status()

            if response.status_code == 204:
                return None

            if return_bytes:
                return response.content

            content_type = response.headers.get("content-type", "")

            if "application/json" in content_type:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode JSON from {url}, returning text instead.")
                    return response.text
            elif "image/" in content_type:
                # Return data-uri for easier processing in default text mode
                b64 = base64.b64encode(response.content).decode("utf-8")
                return f"data:{content_type};base64,{b64}"

            return response.text

        except httpx.HTTPStatusError as e:
            logger.error(f"API Error {e.response.status_code} for {method} {url}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    async def close(self):
        """Closes the underlying HTTP client session."""
        await self.client.aclose()
