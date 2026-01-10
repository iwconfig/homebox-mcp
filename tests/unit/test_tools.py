from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
import httpx
from fastmcp.utilities.types import Image

from homebox_mcp.tools.actions import handle_wipe_inventory, handle_create_missing_thumbnails, handle_ensure_asset_ids
from homebox_mcp.tools.groups import (
    handle_create_group_invitation,
    handle_export_bom,
    handle_get_group,
    handle_update_group,
    handle_get_label_statistics,
    handle_get_location_statistics,
    handle_get_purchase_price_statistics,
)
from homebox_mcp.tools.items import (
    handle_create_item,
    handle_get_item,
    handle_get_item_field_values,
    handle_get_item_link,
    handle_import_items,
    handle_list_items,
    handle_patch_item,
    handle_update_item_attachment,
    handle_upload_item_attachment,
    handle_delete_item,
    handle_get_item_by_asset_id,
    handle_export_items,
    handle_get_item_fields,
    handle_duplicate_item,
    handle_get_item_path,
    handle_get_item_attachment_token,
    handle_delete_item_attachment,
    handle_get_item_maintenance,
    handle_create_item_maintenance,
    handle_get_item_image,
)
from homebox_mcp.tools.labels import (
    handle_create_label,
    handle_get_label,
    handle_list_labels,
    handle_delete_label,
)
from homebox_mcp.tools.locations import (
    handle_create_location,
    handle_get_location,
    handle_get_locations_tree,
    handle_list_locations,
    handle_update_location,
    handle_delete_location,
)
from homebox_mcp.tools.maintenance import (
    handle_query_all_maintenance, 
    handle_update_maintenance_entry,
    handle_delete_maintenance_entry,
)
from homebox_mcp.tools.misc import (
    handle_create_qrcode,
    handle_get_label_image,
    handle_get_status,
    handle_list_currencies,
    handle_search_product_by_barcode,
)
from homebox_mcp.tools.notifiers import handle_update_notifier, handle_list_notifiers, handle_create_notifier, handle_test_notifier, handle_delete_notifier
from homebox_mcp.tools.templates import (
    handle_create_item_from_template,
    handle_create_template,
    handle_get_template,
    handle_list_templates,
    handle_delete_template,
)
from homebox_mcp.tools.users import handle_change_password, handle_delete_user_self, handle_get_user_self, handle_update_user_self, handle_register_user, handle_login_user, handle_logout_user


@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Default mock for get_user_self used by guardrails
    client.get_user_self.return_value = {"item": {"email": "safe@example.com", "id": "user-123"}}
    # Fallback for request if needed
    client.request.return_value = {"item": {"email": "safe@example.com", "id": "user-123"}}
    client.get_web_url = lambda rt, id: f"http://mock-homebox/{rt}/{id}"
    return client


# --- Tool Logic Tests ---


@pytest.mark.asyncio
async def test_wipe_inventory_safety_lock(mock_client, monkeypatch):
    """Verify that wipe_inventory fails if the safety switch is false."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "false")
    with pytest.raises(ValueError, match="Action 'wipe_inventory' is disabled via safety switch"):
        await handle_wipe_inventory(mock_client)


@pytest.mark.asyncio
async def test_wipe_inventory_success_flow(mock_client, monkeypatch):
    """Verify that wipe_inventory calls the API correctly when allowed."""
    monkeypatch.setenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "true")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "")
    
    mock_client.get_user_self.return_value = {"item": {"email": "safe@ex.com", "id": "safe-id"}}
    mock_client.wipe_inventory.return_value = {"completed": 10}
    
    res = await handle_wipe_inventory(mock_client, wipe_labels=True)
    assert "Wipe inventory" in res
    assert mock_client.wipe_inventory.call_count == 1
    assert mock_client.wipe_inventory.call_args[0][0]["wipeLabels"] is True


@pytest.mark.asyncio
async def test_create_item_full_enrichment(mock_client):
    """Verify the two-step creation and merging of all fields."""
    mock_client.create_item.return_value = {
        "id": "itm-1",
        "name": "Tool",
        "location": {"id": "l1"},
        "labels": [{"id": "lab1"}],
        "quantity": 1,
    }
    mock_client.update_item.return_value = {"id": "itm-1", "name": "Tool", "notes": "Merged"}

    await handle_create_item(mock_client, name="Tool", location_id="l1", notes="Merged", purchase_price=9.99)

    # Check update_item payload
    args, kwargs = mock_client.update_item.call_args
    assert args[0] == "itm-1"
    payload = args[1]
    assert payload["notes"] == "Merged"
    assert payload["purchasePrice"] == "9.99"
    # Ensure the 0001 dates are sent
    assert payload["purchaseTime"] == "0001-01-01T00:00:00Z"
    assert payload["warrantyExpires"] == "0001-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_get_item_link_multiple_matches(mock_client):
    """Verify behavior when multiple items match the query."""
    mock_client.request.return_value = {
        "items": [{"id": "1", "name": "Cable A", "assetId": "A1"}, {"id": "2", "name": "Cable B", "assetId": "A2"}]
    }
    res = await handle_get_item_link(mock_client, query="Cable")
    assert "Found 2 matches" in res
    assert "Cable A" in res
    assert "Cable B" in res


@pytest.mark.asyncio
async def test_create_item_rollback(mock_client):
    """Verify that item is deleted if enrichment fails."""
    mock_client.create_item.return_value = {"id": "itm-1", "name": "Minimal"}
    mock_client.update_item.side_effect = Exception("Enrichment Failed")

    with pytest.raises(Exception, match="Enrichment Failed"):
        await handle_create_item(mock_client, name="Tool", location_id="l1", notes="Enrich")

    assert mock_client.delete_item.call_count == 1
    mock_client.delete_item.assert_called_with("itm-1")


@pytest.mark.asyncio
async def test_create_item_invalid_quantity(mock_client):
    """Verify that providing an invalid quantity raises a ValueError."""
    with pytest.raises(ValueError):
        await handle_create_item(mock_client, name="Tool", location_id="l1", quantity="five")


@pytest.mark.asyncio
async def test_get_item_link_asset_id_detection(mock_client):
    """Verify that it correctly prefixes search with # for numeric IDs."""
    mock_client.request.return_value = {"items": [{"id": "1", "name": "Tool"}]}
    await handle_get_item_link(mock_client, query="123")
    args, kwargs = mock_client.request.call_args
    assert kwargs["params"]["q"] == "#123"


@pytest.mark.asyncio
async def test_upload_item_attachment_base64(mock_client):
    mock_client.upload_item_attachment.return_value = {"id": "att-1"}
    b64 = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5"
        "ErkJggg=="
    )
    res = await handle_upload_item_attachment(mock_client, "itm-1", b64)
    assert res == {"id": "att-1"}


@pytest.mark.asyncio
async def test_upload_item_attachment_file_not_found(mock_client):
    with pytest.raises(FileNotFoundError):
        await handle_upload_item_attachment(mock_client, "itm-1", "/tmp/non-existent-file-123.txt")


@pytest.mark.asyncio
async def test_change_password_404_resilience(mock_client):
    """Verify graceful handling if the Homebox version doesn't support the endpoint."""
    mock_client.get_user_self.return_value = {"item": {"email": "safe@ex.com"}}
    mock_client.change_password.side_effect = Exception("Client error '404 Not Found'")
    
    res = await handle_change_password(mock_client, "old", "new")
    assert "might not be supported in this Homebox version" in res


@pytest.mark.asyncio
async def test_delete_user_api_key_protection(mock_client, monkeypatch):
    monkeypatch.setenv("HOMEBOX_ALLOW_USER_DELETION", "true")
    monkeypatch.setenv("HOMEBOX_API_KEY", "SECRET_KEY")
    mock_client.api_key = "SECRET_KEY"
    monkeypatch.setenv("HOMEBOX_USERNAME", "safe@example.com")

    with pytest.raises(ValueError, match="is disabled for the primary account"):
        await handle_delete_user_self(mock_client)


@pytest.mark.asyncio
async def test_update_location_parent_mapping(mock_client):
    """Verify that update_location correctly maps 'parent' object back to 'parentId'."""
    mock_client.get_location.return_value = {"id": "loc-1", "name": "Child", "parent": {"id": "p-123"}}
    mock_client.update_location.return_value = {"id": "loc-1", "name": "Updated"}
    
    await handle_update_location(mock_client, id="loc-1", name="Updated")
    args, kwargs = mock_client.update_location.call_args
    assert args[1]["parentId"] == "p-123"


@pytest.mark.asyncio
async def test_patch_item_logic(mock_client):
    """Verify partial item update logic."""
    mock_client.patch_item.return_value = {"id": "itm-1", "quantity": 5}
    await handle_patch_item(mock_client, id="itm-1", quantity=5)
    args, kwargs = mock_client.patch_item.call_args
    assert args[1]["quantity"] == 5
    assert "name" not in args[1]


@pytest.mark.asyncio
async def test_update_item_attachment_merging(mock_client):
    """Verify that attachment update fetches existing data first."""
    mock_client.get_item.return_value = {"attachments": [{"id": "att-1", "title": "Old", "type": "manual"}]}
    mock_client.update_item_attachment.return_value = {"id": "att-1", "title": "New", "type": "manual"}
    
    await handle_update_item_attachment(mock_client, id="itm-1", attachment_id="att-1", title="New")
    
    args, kwargs = mock_client.update_item_attachment.call_args
    assert args[2]["title"] == "New"
    assert args[2]["type"] == "manual"  # Preserved


@pytest.mark.asyncio
async def test_get_item_field_values_params(mock_client):
    """Verify that field values are queried with the correct field name."""
    mock_client.get_item_field_values.return_value = ["val1", "val2"]
    await handle_get_item_field_values(mock_client, field="Category")
    mock_client.get_item_field_values.assert_called_with("Category")


@pytest.mark.asyncio
async def test_create_template_payload(mock_client):
    """Verify template creation payload and defaults."""
    mock_client.create_template.return_value = {"id": "t1", "name": "T"}
    await handle_create_template(mock_client, name="T", default_insured=True, include_sold_fields=True)
    args, kwargs = mock_client.create_template.call_args
    payload = args[0]
    assert payload["defaultInsured"] is True
    assert payload["includeSoldFields"] is True
    assert payload["includePurchaseFields"] is False  # Default


@pytest.mark.asyncio
async def test_search_product_barcode_empty(mock_client):
    """Verify behavior when no product is found for a barcode."""
    mock_client.search_product_by_barcode.return_value = []
    res = await handle_search_product_by_barcode(mock_client, "123")
    assert res == []


@pytest.mark.asyncio
async def test_get_label_image_invalid_type(mock_client):
    """Verify error handling for invalid label types."""
    with pytest.raises(ValueError, match="Invalid label type"):
        await handle_get_label_image(mock_client, "123", "invalid")


@pytest.mark.asyncio
async def test_update_notifier_not_found(mock_client):
    """Verify behavior when updating a non-existent notifier."""
    mock_client.list_notifiers.return_value = [{"id": "n1"}]
    with pytest.raises(ValueError, match="not found"):
        await handle_update_notifier(mock_client, id="missing")


@pytest.mark.asyncio
async def test_update_maintenance_entry_not_found(mock_client):
    """Verify behavior when updating a non-existent maintenance entry."""
    mock_client.query_all_maintenance.return_value = [{"id": "m1"}]
    with pytest.raises(ValueError, match="not found"):
        await handle_update_maintenance_entry(mock_client, id="m2")


@pytest.mark.asyncio
async def test_list_items_complex_filters(mock_client):
    """Verify list handling for labels, locations, and parentIds parameters."""
    mock_client.list_items.return_value = {"items": [], "total": 0}

    await handle_list_items(mock_client, labels=["lbl1", "lbl2"], locations=["loc1"], parent_ids=["p1"])

    args, kwargs = mock_client.list_items.call_args
    assert kwargs["labels"] == ["lbl1", "lbl2"]
    assert kwargs["locations"] == ["loc1"]
    assert kwargs["parentIds"] == ["p1"]


@pytest.mark.asyncio
async def test_upload_attachment_from_url_success(mock_client):
    """Verify logic for downloading attachment from a URL."""
    mock_client.upload_item_attachment.return_value = {"id": "att-1"}

    with patch("httpx.AsyncClient") as mock_http:
        mock_http_instance = mock_http.return_value
        mock_http_instance.__aenter__.return_value = mock_http_instance
        mock_response = MagicMock(status_code=200, content=b"fake-image-data", headers={"content-type": "image/jpeg"})
        mock_http_instance.get = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock()

        res = await handle_upload_item_attachment(mock_client, "item-1", "http://example.com/image.jpg")
        assert res == {"id": "att-1"}
        assert mock_client.upload_item_attachment.call_count == 1


@pytest.mark.asyncio
async def test_actions_handlers(mock_client):
    mock_client.create_missing_thumbnails.return_value = {"completed": True}
    await handle_create_missing_thumbnails(mock_client)
    mock_client.create_missing_thumbnails.assert_called_once()

    mock_client.ensure_asset_ids.return_value = {"completed": True}
    await handle_ensure_asset_ids(mock_client)
    mock_client.ensure_asset_ids.assert_called_once()


@pytest.mark.asyncio
async def test_items_read_handlers(mock_client):
    mock_client.get_item.return_value = {"id": "1", "name": "Test"}
    await handle_get_item(mock_client, "1")
    mock_client.get_item.assert_called_with("1")

    mock_client.get_item_by_asset_id.return_value = {"id": "1"}
    await handle_get_item_by_asset_id(mock_client, "1")
    mock_client.get_item_by_asset_id.assert_called_with("1")

    mock_client.export_items.return_value = "csv"
    await handle_export_items(mock_client)
    mock_client.export_items.assert_called_once()


@pytest.mark.asyncio
async def test_locations_handlers(mock_client):
    mock_client.list_locations.return_value = []
    await handle_list_locations(mock_client)
    mock_client.list_locations.assert_called_with(filter_children=False)

    mock_client.get_locations_tree.return_value = []
    await handle_get_locations_tree(mock_client)
    mock_client.get_locations_tree.assert_called_with(with_items=False)


@pytest.mark.asyncio
async def test_labels_handlers(mock_client):
    mock_client.list_labels.return_value = []
    await handle_list_labels(mock_client)
    mock_client.list_labels.assert_called_once()

    mock_client.create_label.return_value = {"id": "1"}
    await handle_create_label(mock_client, "Label")
    assert mock_client.create_label.call_args[0][0]["name"] == "Label"


@pytest.mark.asyncio
async def test_groups_handlers(mock_client):
    mock_client.get_group.return_value = {}
    await handle_get_group(mock_client)
    mock_client.get_group.assert_called_once()

    mock_client.update_group.return_value = {}
    await handle_update_group(mock_client, name="G")
    assert mock_client.update_group.call_args[0][0]["name"] == "G"


@pytest.mark.asyncio
async def test_misc_handlers(mock_client):
    mock_client.get_status.return_value = {}
    await handle_get_status(mock_client)
    mock_client.get_status.assert_called_once()

    mock_client.create_qrcode.return_value = b"qrcode-data"
    res = await handle_create_qrcode(mock_client, "Text")
    assert isinstance(res, Image)
    mock_client.create_qrcode.assert_called_with("Text")


@pytest.mark.asyncio
async def test_maintenance_handlers(mock_client):
    mock_client.query_all_maintenance.return_value = []
    await handle_query_all_maintenance(mock_client)
    mock_client.query_all_maintenance.assert_called_with(status="both")


@pytest.mark.asyncio
async def test_templates_handlers(mock_client):
    mock_client.list_templates.return_value = []
    await handle_list_templates(mock_client)
    mock_client.list_templates.assert_called_once()

    mock_client.create_item_from_template.return_value = {"id": "itm"}
    await handle_create_item_from_template(mock_client, "1", "name", "loc")
    payload = mock_client.create_item_from_template.call_args[0][1]
    assert payload["name"] == "name"


@pytest.mark.asyncio
async def test_delete_handlers_success(mock_client):
    """Verify all delete handlers call the client correctly."""
    assert "Deleted" in await handle_delete_item(mock_client, "1")
    mock_client.delete_item.assert_called_with("1")
    
    assert "Deleted" in await handle_delete_location(mock_client, "1")
    mock_client.delete_location.assert_called_with("1")
    
    assert "Deleted" in await handle_delete_label(mock_client, "1")
    mock_client.delete_label.assert_called_with("1")

    assert "Deleted" in await handle_delete_template(mock_client, "1")
    mock_client.delete_template.assert_called_with("1")

    assert "Deleted" in await handle_delete_maintenance_entry(mock_client, "1")
    mock_client.delete_maintenance_entry.assert_called_with("1")

    assert "Deleted" in await handle_delete_item_attachment(mock_client, "1", "1")
    mock_client.delete_item_attachment.assert_called_with("1", "1")


@pytest.mark.asyncio
async def test_search_product_by_barcode_exception(mock_client):
    """Verify exception handling in barcode search."""
    mock_client.search_product_by_barcode.side_effect = Exception("API Error")
    with pytest.raises(Exception, match="API Error"):
        await handle_search_product_by_barcode(mock_client, "123")


@pytest.mark.asyncio
async def test_import_items_logic(mock_client):
    """Verify import items mocking file read and API call."""
    with patch("anyio.Path.read_bytes", new_callable=AsyncMock) as mock_read:
        mock_read.return_value = b"csv,data"
        with patch("anyio.Path.exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True
            res = await handle_import_items(mock_client, "items.csv")
            assert "imported successfully" in res


@pytest.mark.asyncio
async def test_upload_item_attachment_empty_file(mock_client):
    """Verify handling of empty files."""
    mock_client.upload_item_attachment.return_value = {"id": "att-1"}
    with patch("anyio.Path.read_bytes", new_callable=AsyncMock) as mock_read:
        mock_read.return_value = b""
        with patch("anyio.Path.exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True
            res = await handle_upload_item_attachment(mock_client, "itm-1", "empty.txt")
            assert res == {"id": "att-1"}


@pytest.mark.asyncio
async def test_upload_item_attachment_fallback_mime(mock_client):
    """Verify fallback to application/octet-stream and .bin when unknown."""
    # Data URI with unknown mime
    b64 = "data:unknown/type;base64,AAAA"
    mock_client.upload_item_attachment.return_value = {"id": "att-1"}

    res = await handle_upload_item_attachment(mock_client, "itm-1", b64)
    assert res == {"id": "att-1"}

    args, kwargs = mock_client.upload_item_attachment.call_args
    files = kwargs["files"]
    filename = files["file"][0]
    assert filename.endswith(".bin")


@pytest.mark.asyncio
async def test_upload_attachment_from_url_no_extension(mock_client):
    """Verify that file extension is appended when missing from URL but MIME type is known."""
    mock_client.upload_item_attachment.return_value = {"id": "att-1"}

    with patch("httpx.AsyncClient") as mock_http:
        mock_http_instance = mock_http.return_value
        mock_http_instance.__aenter__.return_value = mock_http_instance

        # Mock response with PNG mime type but no extension in URL
        mock_response = MagicMock(status_code=200, content=b"png-data", headers={"content-type": "image/png"})
        mock_http_instance.get = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock()

        res = await handle_upload_item_attachment(mock_client, "item-1", "http://example.com/random-id")

        assert res == {"id": "att-1"}

        args, kwargs = mock_client.upload_item_attachment.call_args
        files = kwargs["files"]
        filename = files["file"][0]
        # Should have appended .png based on image/png
        assert filename == "random-id.png"
