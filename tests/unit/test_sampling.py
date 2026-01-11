from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx
from homebox_mcp.tools.items import handle_create_item

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Default for guardrails
    client.get_user_self.return_value = {"item": {"email": "safe@example.com", "id": "user-123"}}
    return client

@pytest.fixture
def mock_ctx():
    ctx = AsyncMock()
    return ctx

@pytest.mark.asyncio
async def test_handle_create_item_location_suggestion_accepted(mock_client, mock_ctx):
    """Verify that handle_create_item uses suggested location if accepted."""
    # 1. Mock get_location to fail with 404
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=resp)
    mock_client.get_location.side_effect = error
    
    # 2. Mock list_locations for fuzzy find
    mock_client.list_locations.return_value = [
        {"id": "real-loc-id", "name": "Toolshed"}
    ]
    
    # 3. Mock ctx.sample to return YES
    mock_ctx.sample.return_value = MagicMock(text="YES, use it.")
    
    # 4. Mock successful item creation
    mock_client.create_item.return_value = {
        "id": "new-item-id",
        "name": "Hammer",
        "location": {"id": "real-loc-id"},
    }
    mock_client.update_item.return_value = {"id": "new-item-id"}

    # Call the handler with an invalid ID that matches the name "Toolshed"
    await handle_create_item(
        mock_client, 
        name="Hammer", 
        location_id="tool", # matches "Toolshed"
        ctx=mock_ctx
    )
    
    # Verify that sampling was called
    assert mock_ctx.sample.called
    assert "Toolshed" in mock_ctx.sample.call_args[1]["messages"][0]
    
    # Verify that create_item was called with the SUGGESTED ID
    create_payload = mock_client.create_item.call_args[0][0]
    assert create_payload["locationId"] == "real-loc-id"

@pytest.mark.asyncio
async def test_handle_create_item_location_suggestion_declined(mock_client, mock_ctx):
    """Verify that handle_create_item re-raises 404 if suggestion is declined."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=resp)
    mock_client.get_location.side_effect = error
    
    mock_client.list_locations.return_value = [
        {"id": "real-loc-id", "name": "Toolshed"}
    ]
    
    # Mock ctx.sample to return NO
    mock_ctx.sample.return_value = MagicMock(text="NO")
    
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await handle_create_item(
            mock_client, 
            name="Hammer", 
            location_id="tool",
            ctx=mock_ctx
        )
    assert excinfo.value.response.status_code == 404
    
    # create_item should NOT be called
    assert not mock_client.create_item.called

@pytest.mark.asyncio
async def test_handle_create_item_label_suggestion_accepted(mock_client, mock_ctx):
    """Verify that handle_create_item uses suggested labels if accepted."""
    # 1. Mock get_location to succeed (needed for the first resolve)
    mock_client.get_location.return_value = {"id": "loc-1"}
    
    # 2. Mock get_label to fail with 404 for the name "Fragile"
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=resp)
    mock_client.get_label.side_effect = error
    
    # 3. Mock list_labels for fuzzy find
    mock_client.list_labels.return_value = [
        {"id": "label-uuid-fragile", "name": "Fragile Content"}
    ]
    
    # 4. Mock ctx.sample to return YES
    mock_ctx.sample.return_value = MagicMock(text="YES")
    
    # 5. Mock successful item creation
    mock_client.create_item.return_value = {
        "id": "itm-1",
        "name": "Vase",
        "location": {"id": "loc-1"},
        "labels": [{"id": "label-uuid-fragile"}],
    }
    mock_client.update_item.return_value = {"id": "itm-1"}

    # Call with label name instead of ID
    await handle_create_item(
        mock_client, 
        name="Vase", 
        location_id="loc-1",
        label_ids=["Fragile"],
        ctx=mock_ctx
    )
    
    assert mock_ctx.sample.called
    assert "Fragile Content" in mock_ctx.sample.call_args[1]["messages"][0]
    
    # Verify created with resolved label ID
    create_payload = mock_client.create_item.call_args[0][0]
    assert "label-uuid-fragile" in create_payload["labelIds"]

@pytest.mark.asyncio
async def test_handle_create_item_parent_suggestion_accepted(mock_client, mock_ctx):
    """Verify that handle_create_item uses suggested parent item if accepted."""
    mock_client.get_location.return_value = {"id": "loc-1"}
    
    # Mock get_item (parent) to fail with 404
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=resp)
    mock_client.get_item.side_effect = error
    
    # Mock list_items for fuzzy find
    mock_client.list_items.return_value = {
        "items": [{"id": "parent-uuid", "name": "Main Box"}]
    }
    
    mock_ctx.sample.return_value = MagicMock(text="YES")
    
    mock_client.create_item.return_value = {
        "id": "child-id",
        "name": "Small Item",
        "location": {"id": "loc-1"},
        "parent": {"id": "parent-uuid"},
    }
    mock_client.update_item.return_value = {"id": "child-id"}

    await handle_create_item(
        mock_client, 
        name="Small Item", 
        location_id="loc-1",
        parent_id="Main",
        ctx=mock_ctx
    )
    
    assert mock_ctx.sample.called
    assert "Main Box" in mock_ctx.sample.call_args[1]["messages"][0]
    
    create_payload = mock_client.create_item.call_args[0][0]
    assert create_payload["parentId"] == "parent-uuid"
