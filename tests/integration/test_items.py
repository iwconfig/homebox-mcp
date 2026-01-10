import json
import re
import uuid

import pytest


def get_id(res):
    if hasattr(res, "content"):
        text = res.content[0].text
    else:
        text = res

    if not text:
        return None
    # Try parsing as JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("id")
    except (json.JSONDecodeError, AttributeError):
        pass

    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r"ID: ([a-f0-9\-]+)", text)
    if m:
        return m.group(1)
    return None


@pytest.mark.anyio
async def test_item_lifecycle(server_session):
    # Setup: need a location
    loc_res = await server_session.call_tool("create_location", {"name": "Item-Test-Loc"}, raise_on_error=False)
    loc_id = get_id(loc_res)

    # Create item
    item_name = f"Test-Item-{uuid.uuid4().hex[:6]}"
    res = await server_session.call_tool(
        "create_item", {"name": item_name, "location_id": loc_id, "notes": "Initial Notes", "quantity": 5}
    )
    assert not res.is_error
    item_id = get_id(res)
    assert item_id is not None

    # Get item
    res = await server_session.call_tool("get_item", {"id": item_id}, raise_on_error=False)
    assert not res.is_error
    assert item_name in res.content[0].text

    # Update item
    res = await server_session.call_tool("update_item", {"id": item_id, "notes": "Updated Notes"}, raise_on_error=False)
    assert not res.is_error
    assert "Updated Notes" in res.content[0].text

    # Patch item
    res = await server_session.call_tool("patch_item", {"id": item_id, "quantity": 10}, raise_on_error=False)
    assert not res.is_error
    assert re.search(r'"quantity":\s*10', res.content[0].text)

    # List items
    res = await server_session.call_tool("list_items", {"q": item_name}, raise_on_error=False)
    assert not res.is_error
    assert item_name in res.content[0].text

    # Item Link
    res = await server_session.call_tool("get_item_link", {"query": item_name}, raise_on_error=False)
    assert not res.is_error
    assert "Found" in res.content[0].text

    # Item Path
    res = await server_session.call_tool("get_item_path", {"id": item_id}, raise_on_error=False)
    assert not res.is_error

    # Duplicate item
    res = await server_session.call_tool("duplicate_item", {"id": item_id, "copy_prefix": "Dup-"}, raise_on_error=False)
    assert not res.is_error
    dup_id = get_id(res)
    assert dup_id is not None

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
    await server_session.call_tool("delete_item", {"id": dup_id}, raise_on_error=False)

    # Verify deletion
    res = await server_session.call_tool("get_item", {"id": item_id}, raise_on_error=False)
    assert res.is_error
    assert "404" in res.content[0].text

    await server_session.call_tool("delete_location", {"id": loc_id}, raise_on_error=False)


@pytest.mark.anyio
async def test_item_attachments(server_session):
    # Setup
    loc_res = await server_session.call_tool(
        "create_location", {"name": "Att-Test-Loc"}, raise_on_error=False
    )
    loc_id = get_id(loc_res)
    item_res = await server_session.call_tool(
        "create_item", {"name": "Att-Item", "location_id": loc_id}, raise_on_error=False
    )
    item_id = get_id(item_res)

    # Upload attachment (Base64)
    b64_data = "data:text/plain;base64,VGVzdCBDb250ZW50"
    res = await server_session.call_tool(
        "upload_item_attachment", {"item_id": item_id, "file_path": b64_data, "attachment_type": "attachment"}
    )
    assert not res.is_error

    # Fetch item to find the attachment ID
    item_res = await server_session.call_tool("get_item", {"id": item_id}, raise_on_error=False)
    data = json.loads(item_res.content[0].text)
    att_id = data["attachments"][-1]["id"]

    # Update attachment
    res = await server_session.call_tool(
        "update_item_attachment", {"id": item_id, "attachment_id": att_id, "primary": True}
    )
    assert not res.is_error

    # Get attachment token
    res = await server_session.call_tool(
        "get_item_attachment_token", {"id": item_id, "attachment_id": att_id}, raise_on_error=False
    )
    assert not res.is_error

    # Get item image
    res = await server_session.call_tool("get_item_image", {"id": item_id}, raise_on_error=False)
    assert not res.is_error
    assert res.content[0].type == "image"

    # Delete attachment
    res = await server_session.call_tool(
        "delete_item_attachment", {"id": item_id, "attachment_id": att_id}, raise_on_error=False
    )
    assert not res.is_error

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
    await server_session.call_tool("delete_location", {"id": loc_id}, raise_on_error=False)


@pytest.mark.anyio
async def test_item_fields(server_session):
    # Custom Fields
    res = await server_session.call_tool("get_item_fields", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("get_item_field_values", {"field": "name"}, raise_on_error=False)
    assert not res.is_error


@pytest.mark.anyio
async def test_item_export_import(server_session):
    # Export/Import
    res = await server_session.call_tool("export_items", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("import_items", {"file_path": "/non/existent/file.csv"}, raise_on_error=False)
    assert res.is_error


@pytest.mark.anyio
async def test_item_import_success(server_session, tmp_path):
    """Verify that the system can import items from a valid CSV file."""
    # Create a location first to ensure it exists
    loc_name = f"ImportLoc-{uuid.uuid4().hex[:6]}"
    await server_session.call_tool("create_location", {"name": loc_name}, raise_on_error=False)

    # Create a dummy CSV file with correct HB. prefixes
    csv_file = tmp_path / "inventory.csv"
    csv_file.write_text(f"HB.name,HB.quantity,HB.location\nTestImportItem,5,{loc_name}")

    # Run the tool with the real path
    res = await server_session.call_tool("import_items", {"file_path": str(csv_file)}, raise_on_error=False)
    assert not res.is_error
    assert "imported successfully" in res.content[0].text

    # Verify item was created
    list_res = await server_session.call_tool("list_items", {"q": "TestImportItem"}, raise_on_error=False)
    assert "TestImportItem" in list_res.content[0].text


@pytest.mark.anyio
async def test_item_maintenance_integration(server_session):
    # Maintenance Log
    loc_res = await server_session.call_tool(
        "create_location", {"name": "Maint-Test-Loc"}, raise_on_error=False
    )
    loc_id = get_id(loc_res)
    item_res = await server_session.call_tool(
        "create_item", {"name": "Maint-Test-Item", "location_id": loc_id}, raise_on_error=False
    )
    item_id = get_id(item_res)

    res = await server_session.call_tool(
        "create_item_maintenance", {"id": item_id, "name": "Annual Service", "cost": 150.50}
    )
    assert not res.is_error

    res = await server_session.call_tool("get_item_maintenance", {"id": item_id}, raise_on_error=False)
    assert not res.is_error
    assert "Annual Service" in res.content[0].text

    await server_session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
    await server_session.call_tool("delete_location", {"id": loc_id}, raise_on_error=False)


@pytest.mark.anyio
async def test_list_items_pagination(server_session):
    # Pagination
    res = await server_session.call_tool("list_items", {"page": 1, "page_size": 1}, raise_on_error=False)
    assert not res.is_error
