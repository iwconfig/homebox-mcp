import pytest
import respx
import os
import json
from httpx import Response
from homebox_mcp.client import HomeboxClient

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HOMEBOX_API_KEY", "mock_key")
    monkeypatch.setenv("HOMEBOX_LOCAL_URL", "http://mock-homebox")
    return HomeboxClient()

@pytest.mark.anyio
async def test_client_request_success(client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.post("/test").mock(return_value=Response(200, json={"foo": "bar"}))
        
        data = await client.request("POST", "test", json={"in": 1})
        assert data == {"foo": "bar"}

@pytest.mark.anyio
async def test_client_request_500(client):
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        respx_mock.get("/error").mock(return_value=Response(500, text="Boom"))
        
        with pytest.raises(Exception) as excinfo:
            await client.request("GET", "error")
        
        assert "500" in str(excinfo.value)
        # Verify our logger captured it? (Requires caplog fixture)

@pytest.mark.anyio
async def test_client_wipe_inventory_call(client):
    # This verifies the exact call signature the tool would make
    async with respx.mock(base_url="http://mock-homebox/api/v1") as respx_mock:
        route = respx_mock.post("/actions/wipe-inventory").mock(
            return_value=Response(200, json={"completed": 100})
        )
        
        payload = {
            "wipeLabels": True,
            "wipeLocations": False,
            "wipeMaintenance": False
        }
        data = await client.request("POST", "actions/wipe-inventory", json=payload)
        
        assert data["completed"] == 100
        assert route.called
        assert json.loads(route.calls.last.request.content) == payload