import pytest
import json
from unittest.mock import AsyncMock, patch
from homebox_mcp.tools.actions import handle_wipe_inventory
from homebox_mcp.tools.users import handle_register_user, handle_delete_user_self
from homebox_mcp.tools.items import handle_list_items, handle_create_item, handle_get_item_link
from homebox_mcp.tools.locations import handle_create_location, handle_update_location

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Default mock for users/self used by guardrails
    client.request.return_value = {
        "item": {"email": "test@example.com", "id": "user-123"}
    }
    # get_web_url is a sync method in the real client
    client.get_web_url = lambda rt, id: f"http://mock-homebox/{rt}/{id}"
    return client

# --- Wipe Inventory Logic Tests ---

@pytest.mark.asyncio
async def test_wipe_inventory_safety_lock(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "false")
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_wipe_inventory(mock_client)

@pytest.mark.asyncio
async def test_wipe_inventory_success_flow(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "true")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "")
    mock_client.request.side_effect = [
        {"item": {"email": "safe@ex.com", "id": "safe-id"}}, # users/self check
        {"completed": 10} # actual wipe call
    ]
    res = await handle_wipe_inventory(mock_client, wipe_labels=True)
    assert '"completed": 10' in res
    assert mock_client.request.call_count == 2

# --- Item Tool Logic Tests ---

@pytest.mark.asyncio
async def test_list_items_output_format(mock_client):
    """Verify that list_items formats the output string correctly."""
    mock_client.request.return_value = {
        "items": [{"id": "1", "name": "Hammer", "quantity": 1}],
        "total": 1, "page": 1, "totalPages": 1
    }
    res = await handle_list_items(mock_client, q="tools")
    assert "Found 1 items" in res
    assert "[Hammer]" in res
    assert "ID: 1" in res

@pytest.mark.asyncio
async def test_create_item_enrichment_flow(mock_client):
    """Verify the complex two-step creation and enrichment logic."""
    # Step 1: Return minimalist created item
    # Step 2: Return detailed object for enrichment template
    # Step 3: Return final item after PUT
    mock_client.request.side_effect = [
        {"id": "new-item-id"}, # POST response
        {"id": "new-item-id", "name": "Hammer", "location": {"id": "loc-1"}}, # GET response
        {"id": "new-item-id", "name": "Hammer", "notes": "Solid Hammer"} # PUT response
    ]
    
    res = await handle_create_item(
        mock_client, 
        name="Hammer", 
        locationId="loc-1", 
        notes="Solid Hammer",
        purchasePrice=19.99
    )
    
    assert "Solid Hammer" in res
    assert mock_client.request.call_count == 3
    # Verify the PUT (3rd call) contains the stringified price
    args, kwargs = mock_client.request.call_args_list[2]
    assert kwargs["json"]["purchasePrice"] == "19.99"

@pytest.mark.asyncio
async def test_get_item_link_asset_id_detection(mock_client):
    """Verify that it correctly prefixes search with # for IDs."""
    mock_client.request.return_value = {"items": [{"id": "1", "name": "Tool"}]}
    
    # Test numeric string
    await handle_get_item_link(mock_client, query="123")
    args, kwargs = mock_client.request.call_args
    assert kwargs["params"]["q"] == "#123"

# --- Location Tool Logic Tests ---

@pytest.mark.asyncio
async def test_update_location_merging(mock_client):
    """Verify that update_location merges existing data correctly."""
    mock_client.request.side_effect = [
        {"id": "loc-1", "name": "Old Name", "description": "Old Desc"}, # GET
        {"id": "loc-1", "name": "New Name", "description": "Old Desc"}  # PUT
    ]
    
    await handle_update_location(mock_client, id="loc-1", name="New Name")
    
    # Verify PUT payload preserved description
    args, kwargs = mock_client.request.call_args
    assert kwargs["json"]["name"] == "New Name"
    assert kwargs["json"]["description"] == "Old Desc"

# --- User Tool Logic Tests ---

@pytest.mark.asyncio
async def test_register_user_safety_lock(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_REGISTRATION", "false")
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_register_user(mock_client, "name", "email", "pass")

@pytest.mark.asyncio
async def test_delete_user_primary_protection(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_DELETION", "true")
    monkeypatch.setenv("HOMEBOX_USERNAME", "admin@ex.com")
    mock_client.request.return_value = {
        "item": {"email": "admin@ex.com", "id": "admin-id"}
    }
    with pytest.raises(ValueError, match="disabled for the primary account"):
        await handle_delete_user_self(mock_client)