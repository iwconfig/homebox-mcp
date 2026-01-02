import json
import io
import mimetypes
import logging
from PIL import Image, ImageOps
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def handle_crop_image(
    client: HomeboxClient,
    item_id: str,
    attachment_id: str,
    crop_box: tuple[int, int, int, int] = None
) -> str:
    """
    Crops an image attachment and replaces the original.
    crop_box is (left, top, right, bottom).
    """
    if not crop_box:
        return "Error: No crop_box provided."
        
    try:
        # 1. Download original
        url = f"{client.api_base_url}/items/{item_id}/attachments/{attachment_id}/download"
        headers = {"Authorization": f"Bearer {client.token}"}
        resp = await client.client.get(url, headers=headers)
        resp.raise_for_status()
        
        # 2. Crop
        with io.BytesIO(resp.content) as in_buffer:
            img = Image.open(in_buffer)
            img = ImageOps.exif_transpose(img) # Ensure orientation is correct before cropping
            
            # crop_box is (left, top, right, bottom)
            cropped_img = img.crop(crop_box)
            
            out_buffer = io.BytesIO()
            # Preserve format if possible, or default to JPEG
            fmt = img.format or "JPEG"
            cropped_img.save(out_buffer, format=fmt)
            new_content = out_buffer.getvalue()
            
            file_name = f"cropped_{attachment_id}.{fmt.lower()}"
            mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        # 3. Upload as NEW attachment (to be safe? or replace?)
        # The prompt says "replaces the attachment".
        # But `update_item_attachment` only updates metadata.
        # To replace content, we usually delete and upload.
        # Let's delete the old one and upload the new one.
        
        # Upload new
        files = {'file': (file_name, new_content, mime_type)}
        data = {'name': file_name, 'type': 'photo', 'primary': 'true'}
        
        upload_resp = await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
        
        # Delete old
        await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
        
        return f"Successfully cropped image. New attachment details: {json.dumps(upload_resp, indent=2)}"

    except Exception as e:
        logger.error(f"Crop failed: {e}")
        return f"Error cropping image: {str(e)}"

def register_image_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def crop_item_image(
        item_id: str,
        attachment_id: str,
        crop_box: list[int]
    ) -> str:
        """
        Crops an item's image attachment to remove background/clutter.
        Replaces the existing attachment with the cropped version.
        crop_box: [left, top, right, bottom] in pixels.
        """
        if len(crop_box) != 4:
            return "Error: crop_box must be a list of 4 integers [left, top, right, bottom]."
        return await handle_crop_image(client, item_id, attachment_id, tuple(crop_box))
