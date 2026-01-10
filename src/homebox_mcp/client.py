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

    # --- Item Methods ---

    async def list_items(self, **params) -> dict:
        """
        List items with optional filtering.
        Supported params: q, page, pageSize, labels, locations, parentIds,
        negateLabels, onlyWithoutPhoto, onlyWithPhoto, includeArchived, orderBy
        """
        return await self.request("GET", "items", params=params)

    async def get_item(self, item_id: str) -> dict | None:
        try:
            return await self.request("GET", f"items/{item_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_item_by_asset_id(self, asset_id: str) -> dict | None:
        try:
            return await self.request("GET", f"assets/{asset_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_item(self, payload: dict) -> dict:
        return await self.request("POST", "items", json=payload)

    async def update_item(self, item_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"items/{item_id}", json=payload)

    async def patch_item(self, item_id: str, payload: dict) -> dict:
        return await self.request("PATCH", f"items/{item_id}", json=payload)

    async def delete_item(self, item_id: str):
        await self.request("DELETE", f"items/{item_id}")

    async def get_item_fields(self) -> list[str]:
        return await self.request("GET", "items/fields")

    async def get_item_field_values(self, field: str) -> list[str]:
        return await self.request("GET", "items/fields/values", params={"field": field})

    async def duplicate_item(self, item_id: str, payload: dict) -> dict:
        return await self.request("POST", f"items/{item_id}/duplicate", json=payload)

    async def get_item_path(self, item_id: str) -> list[dict]:
        return await self.request("GET", f"items/{item_id}/path")

    async def get_item_attachment_token(self, item_id: str, attachment_id: str) -> dict:
        return await self.request("GET", f"items/{item_id}/attachments/{attachment_id}")

    async def get_attachment_data(self, item_id: str, attachment_id: str) -> bytes:
        return await self.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)

    async def delete_item_attachment(self, item_id: str, attachment_id: str):
        await self.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")

    async def update_item_attachment(self, item_id: str, attachment_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"items/{item_id}/attachments/{attachment_id}", json=payload)

    async def upload_item_attachment(self, item_id: str, files: dict, data: dict) -> dict:
        return await self.request("POST", f"items/{item_id}/attachments", files=files, data=data)

    async def export_items(self) -> str:
        return await self.request("GET", "items/export")

    async def import_items(self, files: dict):
        await self.request("POST", "items/import", files=files)

    # --- Location Methods ---

    async def list_locations(self, filter_children: bool = False) -> list[dict]:
        params = {"filterChildren": "true" if filter_children else "false"}
        return await self.request("GET", "locations", params=params)

    async def get_locations_tree(self, with_items: bool = False) -> list[dict]:
        params = {"withItems": "true" if with_items else "false"}
        return await self.request("GET", "locations/tree", params=params)

    async def get_location(self, location_id: str) -> dict | None:
        try:
            return await self.request("GET", f"locations/{location_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_location(self, payload: dict) -> dict:
        return await self.request("POST", "locations", json=payload)

    async def update_location(self, location_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"locations/{location_id}", json=payload)

    async def delete_location(self, location_id: str):
        await self.request("DELETE", f"locations/{location_id}")

    # --- Label Methods ---

    async def list_labels(self) -> list[dict]:
        return await self.request("GET", "labels")

    async def get_label(self, label_id: str) -> dict | None:
        try:
            return await self.request("GET", f"labels/{label_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_label(self, payload: dict) -> dict:
        return await self.request("POST", "labels", json=payload)

    async def update_label(self, label_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"labels/{label_id}", json=payload)

    async def delete_label(self, label_id: str):
        await self.request("DELETE", f"labels/{label_id}")

    # --- Maintenance Methods ---

    async def query_all_maintenance(self, status: str = "both") -> list[dict]:
        return await self.request("GET", "maintenance", params={"status": status})

    async def get_item_maintenance(self, item_id: str, status: str = "both") -> list[dict] | None:
        try:
            return await self.request("GET", f"items/{item_id}/maintenance", params={"status": status})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_item_maintenance(self, item_id: str, payload: dict) -> dict:
        return await self.request("POST", f"items/{item_id}/maintenance", json=payload)

    async def update_maintenance_entry(self, entry_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"maintenance/{entry_id}", json=payload)

    async def delete_maintenance_entry(self, entry_id: str):
        await self.request("DELETE", f"maintenance/{entry_id}")

    # --- User Methods ---

    async def get_user_self(self) -> dict:
        return await self.request("GET", "users/self")

    async def update_user_self(self, payload: dict) -> dict:
        return await self.request("PUT", "users/self", json=payload)

    async def delete_user_self(self):
        await self.request("DELETE", "users/self")

    async def change_password(self, payload: dict):
        await self.request("PUT", "users/change-password", json=payload)

    async def register_user(self, payload: dict):
        await self.request("POST", "users/register", json=payload)

    # --- Action Methods ---

    async def create_missing_thumbnails(self) -> dict:
        return await self.request("POST", "actions/create-missing-thumbnails")

    async def ensure_asset_ids(self) -> dict:
        return await self.request("POST", "actions/ensure-asset-ids")

    async def ensure_import_refs(self) -> dict:
        return await self.request("POST", "actions/ensure-import-refs")

    async def set_primary_photos(self) -> dict:
        return await self.request("POST", "actions/set-primary-photos")

    async def zero_item_time_fields(self) -> dict:
        return await self.request("POST", "actions/zero-item-time-fields")

    async def wipe_inventory(self, payload: dict) -> dict:
        return await self.request("POST", "actions/wipe-inventory", json=payload)

    # --- Group Methods ---

    async def get_group(self) -> dict:
        return await self.request("GET", "groups")

    async def update_group(self, payload: dict) -> dict:
        return await self.request("PUT", "groups", json=payload)

    async def create_group_invitation(self, payload: dict) -> dict:
        return await self.request("POST", "groups/invitations", json=payload)

    async def get_group_statistics(self) -> dict:
        return await self.request("GET", "groups/statistics")

    async def get_group_statistics_labels(self) -> list[dict]:
        return await self.request("GET", "groups/statistics/labels")

    async def get_group_statistics_locations(self) -> list[dict]:
        return await self.request("GET", "groups/statistics/locations")

    async def get_purchase_price_statistics(self, start: str = None, end: str = None) -> dict:
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self.request("GET", "groups/statistics/purchase-price", params=params)

    # --- Template Methods ---

    async def list_templates(self) -> list[dict]:
        return await self.request("GET", "templates")

    async def create_template(self, payload: dict) -> dict:
        return await self.request("POST", "templates", json=payload)

    async def get_template(self, template_id: str) -> dict:
        return await self.request("GET", f"templates/{template_id}")

    async def update_template(self, template_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"templates/{template_id}", json=payload)

    async def delete_template(self, template_id: str):
        await self.request("DELETE", f"templates/{template_id}")

    async def create_item_from_template(self, template_id: str, payload: dict) -> dict:
        return await self.request("POST", f"templates/{template_id}/create-item", json=payload)

    # --- Notifier Methods ---

    async def list_notifiers(self) -> list[dict]:
        return await self.request("GET", "notifiers")

    async def create_notifier(self, payload: dict) -> dict:
        return await self.request("POST", "notifiers", json=payload)

    async def update_notifier(self, notifier_id: str, payload: dict) -> dict:
        return await self.request("PUT", f"notifiers/{notifier_id}", json=payload)

    async def delete_notifier(self, notifier_id: str):
        await self.request("DELETE", f"notifiers/{notifier_id}")

    async def test_notifier(self, payload: dict):
        await self.request("POST", "notifiers/test", json=payload)

    # --- Misc Methods ---

    async def get_status(self) -> dict:
        return await self.request("GET", "status")

    async def export_bom(self) -> str:
        return await self.request("GET", "reporting/bill-of-materials")

    async def list_currencies(self) -> list[dict]:
        return await self.request("GET", "currencies")

    async def create_qrcode(self, text: str) -> bytes:
        return await self.request("GET", "qrcode", params={"data": text}, return_bytes=True)

    async def get_label_image(self, api_type: str, item_id: str, print_label: bool = False) -> bytes:
        params = {"print": str(print_label).lower()}
        return await self.request("GET", f"labelmaker/{api_type}/{item_id}", params=params, return_bytes=True)

    async def search_product_by_barcode(self, barcode: str) -> list[dict]:
        return await self.request("GET", "products/search-from-barcode", params={"productEAN": barcode})
