import pytest
import respx
import json
import base64
from httpx import Response
from datetime import datetime, timedelta, timezone
from homebox_mcp.client import HomeboxClient

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HOMEBOX_API_KEY", "")
    monkeypatch.setenv("HOMEBOX_USERNAME", "testuser")
    monkeypatch.setenv("HOMEBOX_PASSWORD", "testpass")
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://mock-homebox")
    return HomeboxClient()

@pytest.fixture
def api_key_client(monkeypatch):
    monkeypatch.setenv("HOMEBOX_API_KEY", "sk_123")
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://mock-homebox")
    return HomeboxClient()

# --- Auth & Initialization Tests ---

def test_client_init_defaults(monkeypatch):
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://env-url")
    c = HomeboxClient()
    assert c.local_url == "http://env-url"
    assert c.use_lan_api is True

@pytest.mark.anyio
async def test_login_success(client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.post("/users/login").mock(return_value=Response(200, json={
            "token": "Bearer new-token",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }))
        
        await client.login()
        assert client.token == "new-token"
        assert client.token_expiry > datetime.now(timezone.utc)

@pytest.mark.anyio
async def test_token_auto_refresh(client):
    """Verify that request() automatically refreshes token if it's about to expire."""
    client.token = "old-token"
    client.token_expiry = datetime.now(timezone.utc) + timedelta(minutes=2)
    
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        # Mock refresh call
        refresh_route = respx_mock.get("/users/refresh").mock(return_value=Response(200, json={
            "token": "Bearer refreshed-token",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }))
        # Mock actual request
        data_route = respx_mock.get("/data").mock(return_value=Response(200, json={"ok": True}))
        
        await client.request("GET", "data")
        
        assert refresh_route.called
        assert data_route.called
        assert client.token == "refreshed-token"

# --- Request Handling Tests ---

@pytest.mark.anyio
async def test_request_204_no_content(api_key_client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.delete("/items/1").mock(return_value=Response(204))
        res = await api_key_client.request("DELETE", "items/1")
        assert res is None

@pytest.mark.anyio
async def test_request_image_bytes(api_key_client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        img_data = b"fake-image-bytes"
        respx_mock.get("/img").mock(return_value=Response(
            200, content=img_data, headers={"Content-Type": "image/png"}
        ))
        
        res = await api_key_client.request("GET", "img")
        assert res == img_data

@pytest.mark.anyio
async def test_request_plain_text(api_key_client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.get("/text").mock(return_value=Response(
            200, text="Hello World", headers={"Content-Type": "text/plain"}
        ))
        res = await api_key_client.request("GET", "text")
        assert res == "Hello World"

@pytest.mark.anyio
async def test_request_error_handling(api_key_client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.get("/secret").mock(return_value=Response(403, text="Forbidden access"))
        
        with pytest.raises(Exception) as excinfo:
            await api_key_client.request("GET", "secret")
        assert "403" in str(excinfo.value)

    @pytest.mark.anyio
    async def test_request_json_decode_error(api_key_client):
        """Verify graceful handling when server returns application/json header but invalid body."""
        async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
            # It should raise HTTPStatusError because of 500, but let's see if we can read the text
            # wait, request() raises raise_for_status(). 
            # If we change the status to 200 for this test to check decoding logic only:
            respx_mock.get("/ok-but-bad-json").mock(return_value=Response(
                200, 
                text="Not JSON", 
                headers={"Content-Type": "application/json"}
            ))
            
            res = await api_key_client.request("GET", "ok-but-bad-json")
            assert res == "Not JSON"
# --- URL Helpers Tests ---

def test_api_base_url_logic(monkeypatch):
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://local")
    monkeypatch.setenv("HOMEBOX_WAN_URL", "https://wan")
    c = HomeboxClient()
    
    # Defaults to Local
    c.use_lan_api = True
    assert c.api_base_url == "http://local/api/v1"
    
    # Switch to WAN
    c.use_lan_api = False
    assert c.api_base_url == "https://wan/api/v1"
    
    # Fallback to Local if WAN missing
    c.wan_url = ""
    assert c.api_base_url == "http://local/api/v1"

def test_get_web_url_logic(monkeypatch):
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://local")
    monkeypatch.setenv("HOMEBOX_WAN_URL", "https://wan")
    c = HomeboxClient()
    
    # Default (Local)
    monkeypatch.setenv("LAN_LINKS", "true")
    assert c.get_web_url("item", "123") == "http://local/item/123"
    
    # External Links
    monkeypatch.setenv("LAN_LINKS", "false")
    assert c.get_web_url("item", "123") == "https://wan/item/123"

def test_logout_reverts_credentials(monkeypatch):
    """Rigorous test that logout reverts to ENV credentials."""
    # 1. Setup Env
    monkeypatch.setenv("HOMEBOX_USERNAME", "env_user")
    monkeypatch.setenv("HOMEBOX_PASSWORD", "env_pass")
    
    from homebox_mcp.client import HomeboxClient
    from unittest.mock import AsyncMock

    c = HomeboxClient()
    assert c.username == "env_user"
    
    # 2. Manual Login change
    c.login = AsyncMock() 
    c.username = "manual_user"
    c.password = "manual_pass"
    c.api_key = None
    
    assert c.username == "manual_user"
    
    # 3. Logout
    c.logout()
    
    # 4. Assert Reversion
    assert c.username == "env_user"
    assert c.password == "env_pass"
