import pytest
import io
from PIL import Image, ImageOps
from unittest.mock import AsyncMock, MagicMock
from homebox_mcp.resources.images import fetch_and_anonymize_image

@pytest.mark.asyncio
async def test_image_anonymization_strips_exif():
    """Verify that fetch_and_anonymize_image removes EXIF metadata."""
    client = MagicMock()
    client.api_base_url = "http://mock"
    client.token = "token"
    
    # 1. Create an image with EXIF data (using a simple UserComment or similar)
    # We can use PIL to add some basic EXIF
    img = Image.new('RGB', (100, 100), color='blue')
    exif = img.getexif()
    # Tag 0x9286 is UserComment
    exif[0x9286] = "Sensitive Metadata"
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', exif=exif)
    img_with_exif = img_byte_arr.getvalue()
    
    # Verify the test image actually has EXIF
    test_img = Image.open(io.BytesIO(img_with_exif))
    assert test_img.getexif().get(0x9286) == "Sensitive Metadata"
    
    # 2. Mock the client to return this image
    # The client.request for metadata
    client.request = AsyncMock(return_value={"id": "att1", "title": "test"})
    # The raw httpx client for the download
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = img_with_exif
    client.client.get = AsyncMock(return_value=mock_resp)
    
    # 3. Run through the anonymizer
    result_bytes = await fetch_and_anonymize_image(client, "item1", "att1")
    
    # 4. Verify result has NO EXIF
    clean_img = Image.open(io.BytesIO(result_bytes))
    # clean_img.getexif() might return an empty dict or None-like object
    clean_exif = clean_img.getexif()
    assert 0x9286 not in clean_exif
    assert len(clean_exif) == 0
