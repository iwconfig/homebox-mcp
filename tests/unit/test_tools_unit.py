import pytest
from unittest.mock import AsyncMock, patch
from homebox_mcp.tools.actions import handle_wipe_inventory
from homebox_mcp.tools.users import handle_register_user, handle_delete_user_self

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Default mock for users/self used by guardrails
    client.request.return_value = {
        "item": {"email": "test@example.com", "id": "user-123"}
    }
    return client

# --- Wipe Inventory Logic Tests ---

@pytest.mark.asyncio
async def test_wipe_inventory_safety_lock(mock_client, monkeypatch):
    """Verify that wipe_inventory fails if the safety switch is false."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "false")
    
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_wipe_inventory(mock_client)

@pytest.mark.asyncio
async def test_wipe_inventory_blocked_for_protected_user(mock_client, monkeypatch):
    """Verify that wipe_inventory fails if the user is protected, even if enabled."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "true")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "test@example.com")
    
    # Mock client to return the protected user
    mock_client.request.return_value = {
        "item": {"email": "test@example.com", "id": "user-123"}
    }
    
    with pytest.raises(ValueError, match="Action 'wipe_inventory' is disabled for user 'test@example.com'"):
        await handle_wipe_inventory(mock_client)

@pytest.mark.asyncio
async def test_wipe_inventory_success_flow(mock_client, monkeypatch):
    """Verify that wipe_inventory calls the API correctly when allowed."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "true")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "") # Not protected
    
    mock_client.request.side_effect = [
        {"item": {"email": "safe@ex.com", "id": "safe-id"}}, # for users/self check
        {"completed": 10} # for actual wipe call
    ]
    
    res = await handle_wipe_inventory(mock_client, wipe_labels=True)
    
    assert '"completed": 10' in res
    # Verify the second call was the actual wipe with correct payload
    assert mock_client.request.call_count == 2
    args, kwargs = mock_client.request.call_args
    assert args[1] == "actions/wipe-inventory"
    assert kwargs["json"]["wipeLabels"] is True

# --- User Tool Logic Tests ---

@pytest.mark.asyncio
async def test_register_user_safety_lock(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_REGISTRATION", "false")
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_register_user(mock_client, "name", "email", "pass")

@pytest.mark.asyncio
async def test_delete_user_safety_lock(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_DELETION", "false")
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_delete_user_self(mock_client)

@pytest.mark.asyncio
async def test_delete_user_primary_protection(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_DELETION", "true")
    monkeypatch.setenv("HOMEBOX_USERNAME", "admin@ex.com")
    
    mock_client.request.return_value = {
        "item": {"email": "admin@ex.com", "id": "admin-id"}
    }
    
    with pytest.raises(ValueError, match="disabled for the primary account"):
        await handle_delete_user_self(mock_client)
