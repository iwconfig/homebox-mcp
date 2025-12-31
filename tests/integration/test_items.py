import pytest
import re
import uuid
import json
import base64

def get_id(text):
    if not text: return None
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    m = re.search(r'ID: ([a-f0-9\-]+)', text)
    if m: return m.group(1)
    return None

@pytest.mark.anyio
async def test_item_lifecycle(server_session):
    # Setup: need a location
    loc_res = await server_session.call_tool("create_location", {"name": "Item-Test-Loc"})
    loc_id = get_id(loc_res.content[0].text)
    
    # Create item
    item_name = f"Test-Item-{uuid.uuid4().hex[:6]}"
    res = await server_session.call_tool("create_item", {
        "name": item_name, 
        "locationId": loc_id,
        "notes": "Initial Notes",
        "quantity": 5
    })
    assert not getattr(res, "isError", False)
    item_id = get_id(res.content[0].text)
    assert item_id is not None

    # Get item
    res = await server_session.call_tool("get_item", {"id": item_id})
    assert not getattr(res, "isError", False)
    assert item_name in res.content[0].text

    # Update item
    res = await server_session.call_tool("update_item", {"id": item_id, "notes": "Updated Notes"})
    assert not getattr(res, "isError", False)
    assert "Updated Notes" in res.content[0].text

    # Patch item
    res = await server_session.call_tool("patch_item", {"id": item_id, "quantity": 10})
    assert not getattr(res, "isError", False)
    assert '"quantity": 10' in res.content[0].text

    # List items
    res = await server_session.call_tool("list_items", {"q": item_name})
    assert not getattr(res, "isError", False)
    assert item_name in res.content[0].text

    # Item Link
    res = await server_session.call_tool("get_item_link", {"query": item_name})
    assert not getattr(res, "isError", False)
    assert "Found" in res.content[0].text

    # Get by Asset ID
    item_data_res = await server_session.call_tool("get_item", {"id": item_id})
    asset_id_match = re.search(r'"assetId":\s*"([^"]+)"', item_data_res.content[0].text)
    if asset_id_match:
        asset_id = asset_id_match.group(1)
        res = await server_session.call_tool("get_item_by_asset_id", {"id": asset_id})
        assert not getattr(res, "isError", False)

    # Item Path
    res = await server_session.call_tool("get_item_path", {"id": item_id})
    assert not getattr(res, "isError", False)

    # Duplicate item
    res = await server_session.call_tool("duplicate_item", {"id": item_id, "copyPrefix": "Dup-"})
    assert not getattr(res, "isError", False)
    dup_id = get_id(res.content[0].text)
    assert dup_id is not None

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_item", {"id": dup_id})
    await server_session.call_tool("delete_location", {"id": loc_id})

@pytest.mark.anyio
async def test_item_attachments(server_session):
    # Setup
    loc_res = await server_session.call_tool("create_location", {"name": "Att-Test-Loc"})
    loc_id = get_id(loc_res.content[0].text)
    item_res = await server_session.call_tool("create_item", {"name": "Att-Item", "locationId": loc_id})
    item_id = get_id(item_res.content[0].text)

    # Upload attachment (Base64)
    b64_data = "data:text/plain;base64,VGVzdCBDb250ZW50"
    res = await server_session.call_tool("upload_item_attachment", {
        "item_id": item_id,
        "file_path": b64_data,
        "attachment_type": "attachment"
    })
    assert not getattr(res, "isError", False)
    
    json_match = re.search(r"\{.*\}", res.content[0].text, re.DOTALL)
    data = json.loads(json_match.group(0))
    att_id = data["attachments"][-1]["id"]

    # Update attachment
    res = await server_session.call_tool("update_item_attachment", {
        "id": item_id,
        "attachment_id": att_id,
        "title": "New Title"
    })
    assert not getattr(res, "isError", False)

    # Get attachment token
    res = await server_session.call_tool("get_item_attachment_token", {
        "id": item_id,
        "attachment_id": att_id
    })
    assert not getattr(res, "isError", False)

    # Delete attachment
    res = await server_session.call_tool("delete_item_attachment", {
        "id": item_id,
        "attachment_id": att_id
    })
    assert not getattr(res, "isError", False)

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_location", {"id": loc_id})

@pytest.mark.anyio
async def test_item_fields(server_session):
    # Custom Fields
    res = await server_session.call_tool("get_item_fields", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("get_item_field_values", {"field": "name"})
    assert not getattr(res, "isError", False)

@pytest.mark.anyio
async def test_item_export_import(server_session):
    # Export/Import
    res = await server_session.call_tool("export_items", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("import_items", {"file_path": "/non/existent/file.csv"})
    assert "Error" in res.content[0].text

@pytest.mark.anyio
async def test_item_import_success(server_session, tmp_path):
    """Verify that the system can import items from a valid CSV file."""
    # Create a location first to ensure it exists
    loc_name = f"ImportLoc-{uuid.uuid4().hex[:6]}"
    await server_session.call_tool("create_location", {"name": loc_name})

    # Create a dummy CSV file with correct HB. prefixes
    csv_file = tmp_path / "inventory.csv"
    csv_file.write_text(f"HB.name,HB.quantity,HB.location\nTestImportItem,5,{loc_name}")
    
    # Run the tool with the real path
    res = await server_session.call_tool("import_items", {"file_path": str(csv_file)})
    assert not getattr(res, "isError", False)
    assert "imported successfully" in res.content[0].text
    
    # Verify item was created
    list_res = await server_session.call_tool("list_items", {"q": "TestImportItem"})
    assert "TestImportItem" in list_res.content[0].text
    
    # Cleanup (optional but good practice)
    # Get ID of created item? List items returns text, parsing ID is hard without regex.
    # The session is transient or cleanable? 
    # For now, relying on eventual cleanup or non-interference.

@pytest.mark.anyio
async def test_item_maintenance_integration(server_session):
    # Maintenance Log
    loc_res = await server_session.call_tool("create_location", {"name": "Maint-Test-Loc"})
    loc_id = get_id(loc_res.content[0].text)
    item_res = await server_session.call_tool("create_item", {"name": "Maint-Test-Item", "locationId": loc_id})
    item_id = get_id(item_res.content[0].text)

    res = await server_session.call_tool("create_item_maintenance", {
        "id": item_id,
        "name": "Annual Service",
        "cost": 150.50
    })
    assert not getattr(res, "isError", False)
    
    res = await server_session.call_tool("get_item_maintenance", {"id": item_id})
    assert not getattr(res, "isError", False)
    assert "Annual Service" in res.content[0].text

    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_location", {"id": loc_id})

@pytest.mark.anyio
async def test_list_items_pagination(server_session):
    # Pagination
    res = await server_session.call_tool("list_items", {"page": 1, "pageSize": 1})
    assert not getattr(res, "isError", False)
    assert "Page 1" in res.content[0].text