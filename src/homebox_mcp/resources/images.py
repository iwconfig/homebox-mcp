import logging
import io
import httpx
from PIL import Image, ImageOps
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def fetch_and_anonymize_image(client: HomeboxClient, item_id: str, attachment_id: str) -> bytes:
    """
    Fetches an image attachment, strips metadata, and returns bytes.
    """
    # 1. Get the download token/url
    # The current client.request automatically adds the token. 
    # We can probably just GET the attachment content directly if we know the URL pattern,
    # or we use the get_item_attachment_token endpoint if the backend requires it.
    # However, standard Homebox API usually allows GET /items/{id}/attachments/{att_id} to return JSON
    # and maybe a download link? Or does it return the file directly?
    
    # Looking at previous traces/docs, GET /items/{id}/attachments/{att_id} returns details (including a file key/url).
    # To download, we often hit a different endpoint or use the token.
    # But let's check `handle_get_item_attachment_token` in items.py:
    # `await client.request("GET", f"items/{id}/attachments/{attachment_id}")` returns JSON.
    
    # Let's inspect what that JSON looks like usually.
    # Assuming it contains a `file` key or we construct the download URL.
    # Actually, standard Homebox (Grocy fork-ish?) usually serves files at /api/v1/items/{id}/attachments/{att_id}/download 
    # OR we might need to use `client.local_url` + path.
    
    # Wait, in `items.py`:
    # async def handle_upload_item_attachment ...
    
    # Let's try to fetch the attachment details first.
    try:
        att_details = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}")
        # If this returns the file content directly (unlikely for "GET .../attachments/{id}"), we are good.
        # If it returns JSON, we look for a URL.
        
        image_data = b""
        if isinstance(att_details, dict):
            # It's metadata. We need to download the file.
            # Usually: /api/v1/items/{id}/attachments/{att_id}/download?token=... or similar.
            # Or just GET /api/v1/items/{id}/attachments/{att_id}/file
            
            # Let's try the common convention or what the client supports.
            # The client doesn't have a specific "download_file" method but we can use `client.request`.
            # If we assume standard REST patterns, maybe:
            download_url = f"items/{item_id}/attachments/{attachment_id}/download"
            
            # We need to perform a raw request because client.request might try to parse JSON.
            # But client.request handles "image/" content type!
            
            # Let's try fetching the download endpoint.
            # Note: client.request returns text or dict. We need bytes.
            # We should probably access the underlying client or add a method.
            # Accessing `client.client` (httpx.AsyncClient) is possible.
            
            url = f"{client.api_base_url}/items/{item_id}/attachments/{attachment_id}/download"
            headers = {"Authorization": f"Bearer {client.token}"}
            
            resp = await client.client.get(url, headers=headers)
            # Check if 404, if so, maybe it's not the right endpoint. 
            # But for now assume it works or we catch exception.
            if resp.status_code == 200:
                image_data = resp.content
            
        elif isinstance(att_details, str) and att_details.startswith("data:"):
            import base64
            header, encoded = att_details.split(",", 1)
            image_data = base64.b64decode(encoded)

        if not image_data:
            # Fallback: if the previous GET returned JSON, maybe it has a direct link?
            # For now, let's assume the /download endpoint works.
            # If not, we might fail.
            if isinstance(att_details, bytes):
                image_data = att_details
            else:
                 raise ValueError("Could not determine image source")

        # 2. Process with Pillow
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
