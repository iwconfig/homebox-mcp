import logging
import io
import httpx
import os
from PIL import Image, ImageOps
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def fetch_image_as_pil(
    client: HomeboxClient, 
    item_id: str, 
    attachment_id: Optional[str] = None, 
    scale: bool = True
) -> Image.Image:
    """
    Fetches an image from Local Inbox or API, transposes EXIF, converts to RGB, 
    and optionally scales it. Returns a clean PIL Image.
    """
    image_data = b""
    
    # 1. Try Local Inbox
    inbox_dir = os.getenv("HOMEBOX_INBOX_DIRECTORY")
    if inbox_dir and os.path.exists(inbox_dir):
        full_path = os.path.join(inbox_dir, item_id)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                with open(full_path, 'rb') as f:
                    image_data = f.read()
            except Exception as e:
                logger.error(f"Failed to read local image {item_id}: {e}")

    # 2. Fallback to API
    if not image_data and attachment_id:
        try:
            image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}")
        except Exception as e:
            logger.error(f"Failed to fetch API image {attachment_id}: {e}")

    if not image_data:
        raise ValueError(f"Could not find image data for {item_id}")

    with io.BytesIO(image_data) as in_buffer:
        img = Image.open(in_buffer)
        img = ImageOps.exif_transpose(img)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        if scale:
            max_dim_val = os.getenv("HOMEBOX_MAX_IMAGE_DIMENSION", "1024")
            if max_dim_val.lower() not in ("off", "-1"):
                try:
                    max_dim = int(max_dim_val)
                    if max(img.size) > max_dim:
                        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                except ValueError:
                    pass
            
        # Create clean copy to strip metadata
        clean_img = Image.new(img.mode, img.size)
        clean_img.paste(img)
        # Preserve original format info
        clean_img.format = img.format
        return clean_img

async def fetch_and_anonymize_image(client: HomeboxClient, item_id: str, attachment_id: str) -> bytes:
    """
    Returns bytes for the agent-facing resource (scaled by default).
    """
    try:
        img = await fetch_image_as_pil(client, item_id, attachment_id, scale=True)
        out_buffer = io.BytesIO()
        img.save(out_buffer, format="JPEG", quality=85)
        return out_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error providing image to agent: {e}")
        raise RuntimeError(f"Failed to process image: {e}")
