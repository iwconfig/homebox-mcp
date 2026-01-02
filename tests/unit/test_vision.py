import pytest
from unittest.mock import AsyncMock, MagicMock
from homebox_mcp.resources.inbox import get_inbox_items
from homebox_mcp.resources.images import fetch_and_anonymize_image
from homebox_mcp.tools.images import handle_crop_image

@pytest.mark.asyncio
async def test_get_inbox_items():
    client = MagicMock()
    # Mocking client.request to return locations and then items
    client.request = AsyncMock(side_effect=[
        # 1. Locations list
        {"items": [{"id": "loc_inbox", "name": "Inbox"}]},
        # 2. Items in inbox
        {"items": [{"id": "item1", "name": "Unknown Item", "attachments": [{"id": "att1", "name": "photo.jpg"}]}]}
    ])
    
    result = await get_inbox_items(client)
    assert "Unknown Item" in result
    assert "homebox://items/item1/attachments/att1/image" in result
    assert "loc_inbox" in client.request.call_args_list[1][1]["params"]["locations"]

@pytest.mark.asyncio
async def test_crop_image_success():
    client = MagicMock()
    client.api_base_url = "http://mock"
    client.token = "token"
    
    # Mock download response
    from PIL import Image
    import io
    
    # Create a dummy image
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()
    
    mock_resp = MagicMock()
    mock_resp.content = img_byte_arr
    mock_resp.raise_for_status = MagicMock()
    
    client.client.get = AsyncMock(return_value=mock_resp)
    
    # Mock upload response
    client.request = AsyncMock(return_value={"id": "new_att"})
    
    result = await handle_crop_image(client, "item1", "att1", crop_box=(10, 10, 50, 50))
    
    assert "Successfully cropped" in result
    assert client.request.call_count == 2 # 1 upload, 1 delete
