import pytest
import io
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from homebox_mcp.resources.inbox import get_inbox_items
from homebox_mcp.tools.images import handle_crop_image, handle_split_item_from_image

@pytest.mark.anyio
async def test_get_inbox_items():
    client = MagicMock()
    # Mocking client.request: 
    # 1. Locations list
    # 2. Items in inbox
    # 3. Item detail (for item1)
    client.request = AsyncMock(side_effect=[
        {"items": [{"id": "loc_inbox", "name": "Inbox"}]},
        {"items": [{"id": "item1", "name": "Unknown Item"}]},
        {"id": "item1", "name": "Unknown Item", "attachments": [{"id": "att1", "name": "photo.jpg"}]}
    ])
    
    result = await get_inbox_items(client)
    assert "Unknown Item" in result
    assert "homebox://items/item1/attachments/att1/image" in result

@pytest.mark.anyio
async def test_crop_image_success():
    client = MagicMock()
    client.api_base_url = "http://mock"
    client.token = "token"
    
    # Mock image content
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_data = img_byte_arr.getvalue()

    # 1. Mock download request (returns bytes)
    # 2. Mock upload request
    # 3. Mock delete request
    client.request = AsyncMock(side_effect=[
        img_data, # GET download
        {"id": "new_att"}, # POST new
        None # DELETE old
    ])
    
    result = await handle_crop_image(client, "item1", "att1", crop_box=(10, 10, 50, 50))
    
    assert "Successfully cropped" in result
    assert client.request.call_count == 3

@pytest.mark.anyio
async def test_split_item_success(tmp_path):
    client = MagicMock()
    
    # Mock LARGE image content (2000x2000)
    img = Image.new('RGB', (200, 200), color='blue')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_data = img_byte_arr.getvalue()

    # Create a local mock file
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    local_file = inbox_dir / "photo.jpg"
    local_file.write_bytes(img_data)
    
    with patch.dict(os.environ, {"HOMEBOX_INBOX_DIRECTORY": str(inbox_dir)}):
        client.request = AsyncMock(side_effect=[
            {"id": "child1"}, # POST
            {"id": "child1", "name": "C1"}, # PUT
            {"id": "child2"}, # POST
            {"id": "child2", "name": "C2"}, # PUT
            {"id": "att_c1"}, # POST att 1
            {"id": "att_c2"}, # POST att 2
        ])

        # Use normalized coordinates (0-1000)
        extracted_objects = [
            {"name": "C1", "locationId": "loc1", "crop_box": [0,0,500,500]}, 
            {"name": "C2", "locationId": "loc1", "crop_box": [500,0,1000,500]}
        ]
        
        result_json = await handle_split_item_from_image(client, "photo.jpg", extracted_objects, source="local")
        result = json.loads(result_json)
        
        assert result["status"] == "success"
        assert len(result["extracted_objects"]) == 2
        assert not local_file.exists()