import logging
import io
import httpx
import os
from PIL import Image, ImageOps
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def fetch_and_anonymize_image(client: HomeboxClient, item_id: str, attachment_id: str) -> bytes:
    """
    Fetches an image from either Homebox API or Local Inbox, strips metadata, and returns bytes.
    """
    image_data = b""
    
    # 1. Try Local Inbox first if configured
    inbox_dir = os.getenv("HOMEBOX_INBOX_DIRECTORY")
    if inbox_dir and os.path.exists(inbox_dir):
        full_path = os.path.join(inbox_dir, item_id)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with open(full_path, 'rb') as f:
                    image_data = f.read()
            except Exception as e:
                logger.error(f"Failed to read local image {item_id}: {e}")

    # 2. Fallback to Homebox API
    if not image_data:
        try:
            att_details = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}")
            
            if isinstance(att_details, bytes):
                image_data = att_details
            elif isinstance(att_details, dict):
                url = f"{client.api_base_url}/items/{item_id}/attachments/{attachment_id}/download"
                headers = {"Authorization": f"Bearer {client.token}"}
                resp = await client.client.get(url, headers=headers)
                if resp.status_code == 200:
                    image_data = resp.content
                
            elif isinstance(att_details, str) and att_details.startswith("data:"):
                import base64
                header, encoded = att_details.split(",", 1)
                image_data = base64.b64decode(encoded)
        except Exception as e:
            logger.error(f"Failed to fetch API image {attachment_id}: {e}")

    if not image_data:
        raise ValueError(f"Could not find image for item {item_id} / attachment {attachment_id}")

    # 3. Process with Pillow
    try:
        with io.BytesIO(image_data) as in_buffer:
            img = Image.open(in_buffer)
            
            # Apply EXIF rotation if present, then strip it.
            img = ImageOps.exif_transpose(img)
            
            # Convert to RGB to avoid issues with saving (e.g. RGBA to JPEG) if we enforce JPEG
            # or keep original format if possible.
            # Let's standardize on JPEG for the agent to ensure compatibility.
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            # Create a new image to ensure no metadata is carried over
            data = list(img.getdata())
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(data)
            
            out_buffer = io.BytesIO()
            clean_img.save(out_buffer, format="JPEG", quality=85)
            return out_buffer.getvalue()

    except Exception as e:
        logger.error(f"Error processing image {attachment_id}: {e}")
        # Return a placeholder error image or raise
        raise RuntimeError(f"Failed to process image: {e}")

def register_image_resource(mcp: FastMCP, client: HomeboxClient):
    @mcp.resource("homebox://items/{item_id}/attachments/{attachment_id}/image", mime_type="image/jpeg")
    async def get_item_image(item_id: str, attachment_id: str) -> bytes:
        """Returns the anonymized (metadata stripped) image data for an attachment."""
        return await fetch_and_anonymize_image(client, item_id, attachment_id)
