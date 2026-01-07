import logging
import io
import httpx
import os
from PIL import Image, ImageOps
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def fetch_and_anonymize_image_as_pil(client: HomeboxClient, item_id: str, attachment_id: str) -> Image.Image:
    """
    Fetches an image, strips metadata, scales it, and returns a PIL Image object.
    """
    image_data = b""
    
    # 1. Try Local Inbox first
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
            image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}")
        except Exception as e:
            logger.error(f"Failed to fetch API image {attachment_id}: {e}")

    if not image_data:
        raise ValueError(f"Could not find image for item {item_id} / attachment {attachment_id}")

    with io.BytesIO(image_data) as in_buffer:
        img = Image.open(in_buffer)
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 3. Scaling
        max_dim = int(os.getenv("HOMEBOX_MAX_IMAGE_DIMENSION", "1024"))
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
        # Create clean copy without metadata
        clean_img = Image.new(img.mode, img.size)
        clean_img.paste(img)
        return clean_img

async def fetch_and_anonymize_image(client: HomeboxClient, item_id: str, attachment_id: str) -> bytes:
    """
    Returns the bytes of an anonymized and scaled image.
    """
    try:
        img = await fetch_and_anonymize_image_as_pil(client, item_id, attachment_id)
        out_buffer = io.BytesIO()
        img.save(out_buffer, format="JPEG", quality=85)
        return out_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error processing image {attachment_id}: {e}")
        raise RuntimeError(f"Failed to process image: {e}")

def register_image_resource(mcp: FastMCP, client: HomeboxClient):
    @mcp.resource("homebox://items/{item_id}/attachments/{attachment_id}/image", mime_type="image/jpeg")
    async def get_item_image(item_id: str, attachment_id: str) -> bytes:
        """Returns the anonymized (metadata stripped) image data for an attachment."""
        return await fetch_and_anonymize_image(client, item_id, attachment_id)
