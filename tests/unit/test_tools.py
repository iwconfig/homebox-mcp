import pytest
import json
import os
from unittest.mock import AsyncMock, patch, MagicMock
from homebox_mcp.tools.actions import handle_wipe_inventory
from homebox_mcp.tools.users import handle_register_user, handle_delete_user_self, handle_change_password
from homebox_mcp.tools.items import (
    handle_list_items, handle_create_item, handle_update_item, 
    handle_upload_item_attachment, handle_import_items, handle_get_item_link,
    handle_patch_item, handle_get_item_field_values, handle_update_item_attachment
)
from homebox_mcp.tools.locations import handle_update_location
from homebox_mcp.tools.misc import handle_search_product_by_barcode, handle_get_label_image
from homebox_mcp.tools.notifiers import handle_update_notifier
from homebox_mcp.tools.maintenance import handle_update_maintenance_entry
from homebox_mcp.tools.templates import handle_create_template

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Default mock for users/self used by guardrails
    client.request.return_value = {
        "item": {"email": "safe@example.com", "id": "user-123"}
    }
    client.get_web_url = lambda rt, id: f"http://mock-homebox/{rt}/{id}"
    return client

# --- Tool Logic Tests ---

@pytest.mark.asyncio
async def test_wipe_inventory_safety_lock(mock_client, monkeypatch):
    """Verify that wipe_inventory fails if the safety switch is false."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "false")
    with pytest.raises(ValueError, match="Safety Lock"):
        await handle_wipe_inventory(mock_client)

@pytest.mark.asyncio
async def test_wipe_inventory_success_flow(mock_client, monkeypatch):
    """Verify that wipe_inventory calls the API correctly when allowed."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "true")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "")
    mock_client.request.side_effect = [
        {"item": {"email": "safe@ex.com", "id": "safe-id"}}, # users/self check
        {"completed": 10} # actual wipe call
    ]
    res = await handle_wipe_inventory(mock_client, wipe_labels=True)
    assert '"completed": 10' in res
    assert mock_client.request.call_count == 2

@pytest.mark.asyncio
async def test_create_item_full_enrichment(mock_client):
    """Verify the two-step creation and merging of all fields."""
    mock_client.request.side_effect = [
        { # POST returns created item (now used as base)
            "id": "itm-1", "name": "Tool", "location": {"id": "l1"}, 
            "labels": [{"id": "lab1"}], "quantity": 1
        },
        {"id": "itm-1", "name": "Tool", "notes": "Merged"} # PUT (final)
    ]
    
    await handle_create_item(
        mock_client, name="Tool", locationId="l1", 
        notes="Merged", purchasePrice=9.99
    )
    
    # Check PUT payload (2nd call, since GET was removed)
    args, kwargs = mock_client.request.call_args_list[1]
    payload = kwargs["json"]
    assert payload["notes"] == "Merged"
    assert payload["purchasePrice"] == "9.99"
    # Ensure the 0001 dates are sent to prevent Go-backend issues
    assert payload["purchaseTime"] == "0001-01-01T00:00:00Z"
    assert payload["warrantyExpires"] == "0001-01-01T00:00:00Z"

@pytest.mark.asyncio
async def test_get_item_link_multiple_matches(mock_client):
    """Verify behavior when multiple items match the query."""
    mock_client.request.return_value = {
        "items": [
            {"id": "1", "name": "Cable A", "assetId": "A1"},
            {"id": "2", "name": "Cable B", "assetId": "A2"}
        ]
    }
    res = await handle_get_item_link(mock_client, query="Cable")
    assert "Found 2 matches" in res
    assert "Cable A" in res
    assert "Cable B" in res

@pytest.mark.asyncio
async def test_create_item_rollback(mock_client):
    """Verify that item is deleted if enrichment fails."""
    mock_client.request.side_effect = [
        {"id": "itm-1", "name": "Minimal"}, # POST
        Exception("Enrichment Failed"), # PUT
        None # DELETE (rollback)
    ]
    
    with pytest.raises(Exception, match="Enrichment Failed"):
         await handle_create_item(mock_client, name="Tool", locationId="l1", notes="Enrich")
         
    # Verify 3 calls: POST, PUT (fail), DELETE
    assert mock_client.request.call_count == 3
    assert mock_client.request.call_args_list[2][0] == ("DELETE", "items/itm-1")

@pytest.mark.asyncio
async def test_create_item_invalid_quantity(mock_client):
    """Verify that providing an invalid quantity raises a ValueError."""
    with pytest.raises(ValueError):
        await handle_create_item(mock_client, name="Tool", locationId="l1", quantity="five")


@pytest.mark.asyncio
async def test_get_item_link_asset_id_detection(mock_client):
    """Verify that it correctly prefixes search with # for numeric IDs."""
    mock_client.request.return_value = {"items": [{"id": "1", "name": "Tool"}]}
    await handle_get_item_link(mock_client, query="123")
    args, kwargs = mock_client.request.call_args
    assert kwargs["params"]["q"] == "#123"

@pytest.mark.asyncio
async def test_upload_item_attachment_base64(mock_client):
    mock_client.request.return_value = {"id": "att-1"}
    b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    res = await handle_upload_item_attachment(mock_client, "itm-1", b64)
    assert "uploaded successfully" in res

@pytest.mark.asyncio
async def test_upload_item_attachment_file_not_found(mock_client):
    res = await handle_upload_item_attachment(mock_client, "itm-1", "/tmp/non-existent-file-123.txt")
    assert "File not found" in res

@pytest.mark.asyncio
async def test_change_password_404_resilience(mock_client):
    """Verify graceful handling if the Homebox version doesn't support the endpoint."""
    mock_client.request.side_effect = [
        {"item": {"email": "safe@ex.com"}}, # GET self
        Exception("Client error '404 Not Found'") # PUT change-password
    ]
    res = await handle_change_password(mock_client, "old", "new")
    assert "might not be supported in this Homebox version" in res

@pytest.mark.asyncio
async def test_delete_user_api_key_protection(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_DELETION", "true")
    monkeypatch.setenv("HOMEBOX_API_KEY", "SECRET_KEY")
    mock_client.api_key = "SECRET_KEY"
    
    with pytest.raises(ValueError, match="associated with the environment API Key"):
        await handle_delete_user_self(mock_client)

@pytest.mark.asyncio
async def test_update_location_parent_mapping(mock_client):
    """Verify that update_location correctly maps 'parent' object back to 'parentId'."""
    mock_client.request.side_effect = [
        {"id": "loc-1", "name": "Child", "parent": {"id": "p-123"}}, # GET
        {"id": "loc-1", "name": "Updated"} # PUT
    ]
    await handle_update_location(mock_client, id="loc-1", name="Updated")
    args, kwargs = mock_client.request.call_args
    assert kwargs["json"]["parentId"] == "p-123"

@pytest.mark.asyncio
async def test_patch_item_logic(mock_client):
    """Verify partial item update logic."""
    mock_client.request.return_value = {"id": "itm-1", "quantity": 5}
    await handle_patch_item(mock_client, id="itm-1", quantity=5)
    args, kwargs = mock_client.request.call_args
    assert kwargs["json"]["quantity"] == 5
    assert "name" not in kwargs["json"]

@pytest.mark.asyncio
async def test_update_item_attachment_merging(mock_client):
    """Verify that attachment update fetches existing data first."""
    mock_client.request.side_effect = [
        {"attachments": [{"id": "att-1", "title": "Old", "type": "manual"}]}, # GET item
        {"id": "att-1", "title": "New", "type": "manual"} # PUT attachment
    ]
    await handle_update_item_attachment(mock_client, id="itm-1", attachment_id="att-1", title="New")
    # Verify the second call was a PUT with merged data
    args, kwargs = mock_client.request.call_args
    assert args[0] == "PUT"
    assert kwargs["json"]["title"] == "New"
    assert kwargs["json"]["type"] == "manual" # Preserved

@pytest.mark.asyncio
async def test_get_item_field_values_params(mock_client):
    """Verify that field values are queried with the correct field name."""
    mock_client.request.return_value = ["val1", "val2"]
    await handle_get_item_field_values(mock_client, field="Category")
    args, kwargs = mock_client.request.call_args
    assert kwargs["params"]["field"] == "Category"

@pytest.mark.asyncio
async def test_create_template_payload(mock_client):
    """Verify template creation payload and defaults."""
    mock_client.request.return_value = {"id": "t1", "name": "T"}
    await handle_create_template(
        mock_client, name="T", defaultInsured=True, includeSoldFields=True
    )
    args, kwargs = mock_client.request.call_args
    payload = kwargs["json"]
    assert payload["defaultInsured"] is True
    assert payload["includeSoldFields"] is True
    assert payload["includePurchaseFields"] is False # Default

@pytest.mark.asyncio
async def test_search_product_barcode_empty(mock_client):
    """Verify behavior when no product is found for a barcode."""
    mock_client.request.return_value = []
    res = await handle_search_product_by_barcode(mock_client, "123")
    assert "No products found" in res

@pytest.mark.asyncio
async def test_get_label_image_invalid_type(mock_client):
    """Verify error handling for invalid label types."""
    res = await handle_get_label_image(mock_client, "invalid", "123")
    assert "Error: Type must be" in res

@pytest.mark.asyncio
async def test_update_notifier_not_found(mock_client):
    """Verify behavior when updating a non-existent notifier."""
    mock_client.request.return_value = [{"id": "n1"}]
    res = await handle_update_notifier(mock_client, id="missing")
    assert "not found" in res

@pytest.mark.asyncio
async def test_update_maintenance_entry_not_found(mock_client):
    """Verify behavior when updating a non-existent maintenance entry."""
    mock_client.request.return_value = [{"id": "m1"}]
    res = await handle_update_maintenance_entry(mock_client, id="m2")
    assert "not found" in res

@pytest.mark.asyncio
async def test_list_items_complex_filters(mock_client):
    """Verify list handling for labels, locations, and parentIds parameters."""
    mock_client.request.return_value = {"items": [], "total": 0}
    
    await handle_list_items(
        mock_client, 
        labels=["lbl1", "lbl2"], 
        locations=["loc1"], 
        parentIds=["p1"]
    )
    
    # Check that lists were passed correctly to the client request
    args, kwargs = mock_client.request.call_args
    params = kwargs["params"]
    assert params["labels"] == ["lbl1", "lbl2"]
    assert params["locations"] == ["loc1"]
    assert params["parentIds"] == ["p1"]

@pytest.mark.asyncio
async def test_upload_attachment_from_url_success(mock_client):
    """Verify logic for downloading attachment from a URL."""
    mock_client.request.return_value = {"id": "att-1"}
    
    # We must mock the internal httpx.AsyncClient used inside the tool function
    with patch("httpx.AsyncClient") as MockHttp:
        mock_http_instance = MockHttp.return_value
        mock_http_instance.__aenter__.return_value = mock_http_instance
        
        # Mock the download response
        mock_response = MagicMock(
            status_code=200, 
            content=b"fake-image-data", 
            headers={"content-type": "image/jpeg"}
        )
        mock_http_instance.get = AsyncMock(return_value=mock_response)
        # Mock raise_for_status to do nothing
        mock_response.raise_for_status = MagicMock()

        res = await handle_upload_item_attachment(
            mock_client, 
            "item-1", 
            "http://example.com/image.jpg"
        )
        
        assert "uploaded successfully" in res
        
        # Verify Homebox API was called with the downloaded content
        args, kwargs = mock_client.request.call_args
        files = kwargs["files"]
        filename, content, mime = files["file"]
        assert content == b"fake-image-data"
        assert mime == "image/jpeg"

@pytest.mark.asyncio
async def test_upload_attachment_from_url_failure(mock_client):
    """Verify error handling when URL download fails."""
    with patch("httpx.AsyncClient") as MockHttp:
        mock_http_instance = MockHttp.return_value
        mock_http_instance.__aenter__.return_value = mock_http_instance
        
        # Mock a 404 from the external image server
        mock_response = MagicMock(status_code=404)
        # Simulate raise_for_status behavior
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_http_instance.get = AsyncMock(return_value=mock_response)

        res = await handle_upload_item_attachment(
            mock_client, 
            "item-1", 
            "http://example.com/missing.jpg"
        )
        
        assert "Error: Failed to download" in res

@pytest.mark.asyncio
async def test_actions_handlers(mock_client):
    from homebox_mcp.tools.actions import handle_create_missing_thumbnails, handle_ensure_asset_ids
    mock_client.request.return_value = {"completed": True}
    
    await handle_create_missing_thumbnails(mock_client)
    mock_client.request.assert_called_with("POST", "actions/create-missing-thumbnails")
    
    await handle_ensure_asset_ids(mock_client)
    mock_client.request.assert_called_with("POST", "actions/ensure-asset-ids")

@pytest.mark.asyncio
async def test_items_read_handlers(mock_client):
    from homebox_mcp.tools.items import (
        handle_get_item, handle_get_item_by_asset_id, handle_export_items, 
        handle_get_item_fields, handle_duplicate_item, handle_get_item_path, 
        handle_get_item_attachment_token, handle_get_item_maintenance
    )
    mock_client.request.return_value = {"id": "1", "name": "Test"}
    
    await handle_get_item(mock_client, "1")
    mock_client.request.assert_called_with("GET", "items/1")
    
    await handle_get_item_by_asset_id(mock_client, "1")
    mock_client.request.assert_called_with("GET", "assets/1")
    
    await handle_export_items(mock_client)
    mock_client.request.assert_called_with("GET", "items/export")
    
    await handle_get_item_fields(mock_client)
    mock_client.request.assert_called_with("GET", "items/fields")
    
    await handle_duplicate_item(mock_client, "1")
    assert mock_client.request.call_args[0] == ("POST", "items/1/duplicate")
    
    await handle_get_item_path(mock_client, "1")
    mock_client.request.assert_called_with("GET", "items/1/path")
    
    await handle_get_item_attachment_token(mock_client, "1", "att1")
    mock_client.request.assert_called_with("GET", "items/1/attachments/att1")
    
    mock_client.request.return_value = []
    await handle_get_item_maintenance(mock_client, "1")
    assert mock_client.request.call_args[1]["params"]["status"] == "both"

@pytest.mark.asyncio
async def test_locations_handlers(mock_client):
    from homebox_mcp.tools.locations import handle_list_locations, handle_get_locations_tree, handle_get_location, handle_create_location
    
    mock_client.request.return_value = []
    await handle_list_locations(mock_client)
    mock_client.request.assert_called_with("GET", "locations", params={"filterChildren": "false"})
    
    await handle_get_locations_tree(mock_client)
    mock_client.request.assert_called_with("GET", "locations/tree", params={"withItems": "false"})
    
    mock_client.request.return_value = {"id": "1"}
    await handle_get_location(mock_client, "1")
    mock_client.request.assert_called_with("GET", "locations/1")
    
    await handle_create_location(mock_client, "New Loc")
    assert mock_client.request.call_args[1]["json"]["name"] == "New Loc"


@pytest.mark.asyncio
async def test_labels_handlers(mock_client):
    from homebox_mcp.tools.labels import handle_list_labels, handle_create_label, handle_get_label
    
    mock_client.request.return_value = []
    await handle_list_labels(mock_client)
    mock_client.request.assert_called_with("GET", "labels")
    
    mock_client.request.return_value = {"id": "1"}
    await handle_create_label(mock_client, "Label")
    assert mock_client.request.call_args[1]["json"]["name"] == "Label"
    
    await handle_get_label(mock_client, "1")
    mock_client.request.assert_called_with("GET", "labels/1")

@pytest.mark.asyncio
async def test_groups_handlers(mock_client):
    from homebox_mcp.tools.groups import handle_get_group, handle_update_group, handle_create_group_invitation, handle_export_bom
    
    mock_client.request.return_value = {}
    await handle_get_group(mock_client)
    mock_client.request.assert_called_with("GET", "groups")
    
    await handle_update_group(mock_client, name="G")
    assert mock_client.request.call_args[1]["json"]["name"] == "G"
    
    await handle_create_group_invitation(mock_client)
    mock_client.request.assert_called_with("POST", "groups/invitations", json={"uses": 1})
    
    await handle_export_bom(mock_client)
    mock_client.request.assert_called_with("GET", "reporting/bill-of-materials")

@pytest.mark.asyncio
async def test_misc_handlers(mock_client):
    from homebox_mcp.tools.misc import handle_get_status, handle_list_currencies, handle_create_qrcode
    
    mock_client.request.return_value = {}
    await handle_get_status(mock_client)
    mock_client.request.assert_called_with("GET", "status")
    
    mock_client.request.return_value = []
    await handle_list_currencies(mock_client)
    mock_client.request.assert_called_with("GET", "currencies")
    
    mock_client.request.return_value = "data:image..."
    await handle_create_qrcode(mock_client, "Text")
    assert mock_client.request.call_args[1]["params"]["data"] == "Text"

@pytest.mark.asyncio
async def test_maintenance_handlers(mock_client):
    from homebox_mcp.tools.maintenance import handle_query_all_maintenance
    mock_client.request.return_value = []
    await handle_query_all_maintenance(mock_client)
    mock_client.request.assert_called_with("GET", "maintenance", params={"status": "both"})

@pytest.mark.asyncio
async def test_templates_handlers(mock_client):
    from homebox_mcp.tools.templates import handle_list_templates, handle_get_template, handle_create_item_from_template
    
    mock_client.request.return_value = []
    await handle_list_templates(mock_client)
    mock_client.request.assert_called_with("GET", "templates")
    
    mock_client.request.return_value = {"id": "1"}
    await handle_get_template(mock_client, "1")
    mock_client.request.assert_called_with("GET", "templates/1")
    
    await handle_create_item_from_template(mock_client, "1", "name", "loc")
    payload = mock_client.request.call_args[1]["json"]
    assert payload["name"] == "name"
    assert payload["locationId"] == "loc"


@pytest.mark.asyncio
async def test_delete_handlers_success(mock_client):
    """Verify all delete handlers call the client correctly."""
    mock_client.request.return_value = None
    
    from homebox_mcp.tools.items import handle_delete_item, handle_delete_item_attachment
    from homebox_mcp.tools.locations import handle_delete_location
    from homebox_mcp.tools.labels import handle_delete_label
    from homebox_mcp.tools.notifiers import handle_delete_notifier
    from homebox_mcp.tools.templates import handle_delete_template
    from homebox_mcp.tools.maintenance import handle_delete_maintenance_entry

    assert "Deleted" in await handle_delete_item(mock_client, "1")
    assert "Deleted" in await handle_delete_location(mock_client, "1")
    assert "Deleted" in await handle_delete_label(mock_client, "1")
    assert "Deleted" in await handle_delete_notifier(mock_client, "1")
    assert "Deleted" in await handle_delete_template(mock_client, "1")
    assert "Deleted" in await handle_delete_maintenance_entry(mock_client, "1")
    assert "Deleted" in await handle_delete_item_attachment(mock_client, "1", "1")

@pytest.mark.asyncio
async def test_search_product_by_barcode_exception(mock_client):
    """Verify exception handling in barcode search."""
    mock_client.request.side_effect = Exception("API Error")
    res = await handle_search_product_by_barcode(mock_client, "123")
    assert "Error searching product" in res
    assert "API Error" in res

@pytest.mark.asyncio
async def test_import_items_logic(mock_client):
    """Verify import items mocking file read and API call."""
    # Mock builtins.open to avoid needing a real file
    with patch("builtins.open", new_callable=MagicMock) as mock_open_file:
        # Setup the file handle mock
        mock_file = mock_open_file.return_value.__enter__.return_value
        mock_file.read.return_value = b"csv,data"
        
        # 1. Test Success Path
        # We must mock os.path.exists to return True so it attempts to open
        with patch("os.path.exists", return_value=True):
            res = await handle_import_items(mock_client, "items.csv")
            assert "imported successfully" in res
            
        # 2. Test Exception Path (inside try/except)
        mock_client.request.side_effect = Exception("Import Failed")
        with patch("os.path.exists", return_value=True):
            res = await handle_import_items(mock_client, "items.csv")
            assert "Failed to import" in res

@pytest.mark.asyncio
async def test_upload_item_attachment_empty_file(mock_client):
    """Verify handling of empty files."""
    with patch("builtins.open", new_callable=MagicMock) as mock_open_file:
        mock_file = mock_open_file.return_value.__enter__.return_value
        mock_file.read.return_value = b""
        
        with patch("os.path.exists", return_value=True):
            # Should proceed but upload empty content
             mock_client.request.return_value = {"id": "att-1"}
             res = await handle_upload_item_attachment(mock_client, "itm-1", "empty.txt")
             assert "uploaded successfully" in res
             args, kwargs = mock_client.request.call_args
             assert kwargs["files"]["file"][1] == b""

@pytest.mark.asyncio
async def test_upload_item_attachment_unreadable_file(mock_client):
    """Verify handling of file read permission errors."""
    with patch("builtins.open", side_effect=PermissionError("Access Denied")):
        with patch("os.path.exists", return_value=True):
             res = await handle_upload_item_attachment(mock_client, "itm-1", "secret.txt")
             assert "Failed to read local file" in res
             assert "Access Denied" in res

@pytest.mark.asyncio
async def test_upload_item_attachment_fallback_mime(mock_client):
    """Verify fallback to application/octet-stream and .bin when unknown."""
    # Data URI with unknown mime
    b64 = "data:unknown/type;base64,AAAA"
    mock_client.request.return_value = {"id": "att-1"}
    
    res = await handle_upload_item_attachment(mock_client, "itm-1", b64)
    assert "uploaded successfully" in res
    
    args, kwargs = mock_client.request.call_args
    filename = kwargs["files"]["file"][0]
    assert filename.endswith(".bin")

@pytest.mark.asyncio
async def test_upload_attachment_from_url_no_extension(mock_client):
    """Verify that file extension is appended when missing from URL but MIME type is known."""
    mock_client.request.return_value = {"id": "att-1"}
    
    with patch("httpx.AsyncClient") as MockHttp:
        mock_http_instance = MockHttp.return_value
        mock_http_instance.__aenter__.return_value = mock_http_instance
        
        # Mock response with PNG mime type but no extension in URL
        mock_response = MagicMock(
            status_code=200, 
            content=b"png-data", 
            headers={"content-type": "image/png"}
        )
        mock_http_instance.get = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock()

        res = await handle_upload_item_attachment(
            mock_client, 
            "item-1", 
            "http://example.com/random-id" 
        )
        
        assert "uploaded successfully" in res
        
        args, kwargs = mock_client.request.call_args
        filename = kwargs["files"]["file"][0]
        # Should have appended .png based on image/png
        assert filename == "random-id.png"

