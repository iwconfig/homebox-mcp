import json
import io
import mimetypes
import logging
import os
from typing import Literal
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
        from ..resources.images import fetch_image_as_pil
        # Fetch full resolution image for cropping
        img = await fetch_image_as_pil(client, item_id, attachment_id, scale=False)

        # Auto-scale normalized coordinates (0-1000)
        target_box = list(crop_box)
        if max(img.size) > 1000 and all(0 <= v <= 1000 for v in target_box):
            w, h = img.size
            target_box = [
                int(target_box[0] * w / 1000),
                int(target_box[1] * h / 1000),
                int(target_box[2] * w / 1000),
                int(target_box[3] * h / 1000)
            ]

        # crop_box is (left, top, right, bottom)
        cropped_img = img.crop(tuple(target_box))
        
        out_buffer = io.BytesIO()
        # Preserve original format or default to JPEG
        fmt = getattr(img, "format", "JPEG") or "JPEG"
        cropped_img.save(out_buffer, format=fmt)
        new_content = out_buffer.getvalue()
        
        file_name = f"cropped_{attachment_id}.{fmt.lower()}"
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        # 3. Upload as NEW attachment
        files = {'file': (file_name, new_content, mime_type)}
        data = {'name': file_name, 'type': 'photo', 'primary': 'true'}
        
        upload_resp = await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
        
        # Delete old
        await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
        
        return f"Successfully cropped image. New attachment details: {json.dumps(upload_resp, indent=2)}"

    except Exception as e:
        logger.error(f"Crop failed: {e}")
        return f"Error cropping image: {str(e)}"

async def handle_rotate_image(
    client: HomeboxClient,
    item_id: str,
    attachment_id: str,
    degrees: int
) -> str:
    """
    Rotates an image attachment and replaces the original.
    degrees: Clockwise rotation amount (internally converted to CCW).
    """
    try:
        from ..resources.images import fetch_image_as_pil
        # Fetch full resolution
        img = await fetch_image_as_pil(client, item_id, attachment_id, scale=False)

        # Standardizing: if user says 90, they usually mean CW.
        # Pillow rotate is CCW. So we negate it.
        # BICUBIC and expand=True for centering and quality
        rotated_img = img.rotate(-degrees, expand=True, resample=Image.BICUBIC)
        
        out_buffer = io.BytesIO()
        fmt = getattr(img, "format", "JPEG") or "JPEG"
        rotated_img.save(out_buffer, format=fmt)
        new_content = out_buffer.getvalue()
        
        file_name = f"rotated_{attachment_id}.{fmt.lower()}"
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        # 3. Upload as NEW attachment
        files = {'file': (file_name, new_content, mime_type)}
        data = {'name': file_name, 'type': 'photo', 'primary': 'true'}
        
        upload_resp = await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
        
        # Delete old
        await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
        
        return f"Successfully rotated image. New attachment details: {json.dumps(upload_resp, indent=2)}"

    except Exception as e:
        logger.error(f"Rotation failed: {e}")
        return f"Error rotating image: {str(e)}"

async def handle_split_item_from_image(
    client: HomeboxClient,
    id: str,
    extracted_objects: list[dict],
    source: Literal["homebox", "local"] = "homebox",
    attachment_id: str = None
) -> str:
    """
    Splits an image into multiple new items.
    """
    from .items import handle_create_item, handle_upload_item_attachment, handle_update_item, handle_delete_item, get_id
    from ..resources.images import fetch_image_as_pil
    
    try:
        # Use full resolution for extraction
        orig_img = await fetch_image_as_pil(client, id, attachment_id, scale=False)
        
        results = []
        for i, obj in enumerate(extracted_objects):
            try:
                # a. Crop
                crop_box = obj.get("crop_box")
                if not crop_box or len(crop_box) != 4:
                    results.append({"status": "error", "error": f"Invalid crop_box for object {i}"})
                    continue
                
                # Auto-scale normalized coordinates (0-1000)
                target_box = list(crop_box)
                if max(orig_img.size) > 1000 and all(0 <= v <= 1000 for v in target_box):
                    w, h = orig_img.size
                    target_box = [
                        int(target_box[0] * w / 1000),
                        int(target_box[1] * h / 1000),
                        int(target_box[2] * w / 1000),
                        int(target_box[3] * h / 1000)
                    ]
                    
                cropped = orig_img.crop(tuple(target_box))
                
                # Apply individual rotation if provided
                # Standard Mathematical Convention: Positive = Counter-Clockwise
                obj_rotation = obj.get("rotation", 0)
                if obj_rotation != 0:
                    # Direct Pillow rotate (CCW)
                    cropped = cropped.rotate(obj_rotation, expand=True, resample=Image.BICUBIC)

                out_buf = io.BytesIO()
                cropped.save(out_buf, format="JPEG", quality=90)
                obj_content = out_buf.getvalue()
                
                # b. Create Item
                create_res = await handle_create_item(
                    client, 
                    name=obj["name"], 
                    locationId=obj["locationId"],
                    description=obj.get("description"),
                    labelIds=obj.get("labelIds"),
                    notes=obj.get("notes"),
                    manufacturer=obj.get("manufacturer"),
                    modelNumber=obj.get("modelNumber"),
                    serialNumber=obj.get("serialNumber")
                )
                item_id = get_id(create_res)
                
                if not item_id:
                    results.append({"status": "error", "error": f"Failed to create item for object {i}: {create_res}"})
                    continue
                
                # c. Upload Attachment
                temp_filename = f"/tmp/split_{item_id}.jpg"
                with open(temp_filename, 'wb') as f:
                    f.write(obj_content)
                    
                await handle_upload_item_attachment(client, item_id, temp_filename, primary=True, attachment_type="photo")
                os.remove(temp_filename)
                
                results.append({"status": "success", "item_id": item_id, "name": obj["name"]})
                
            except Exception as obj_err:
                results.append({"status": "error", "error": str(obj_err)})

        # 4. Cleanup source if at least one object was extracted
        success_count = sum(1 for r in results if r["status"] == "success")
        if success_count > 0:
            if source == "local":
                inbox_dir = os.getenv("HOMEBOX_INBOX_DIRECTORY")
                full_path = os.path.join(inbox_dir, id)
                if os.path.exists(full_path):
                    os.remove(full_path)
            elif source == "homebox":
                await handle_delete_item(client, id)
                
        return json.dumps({
            "status": "success" if success_count == len(extracted_objects) else "partial_success" if success_count > 0 else "error",
            "extracted_objects": results,
            "source_removed": success_count > 0
        }, indent=2)

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return json.dumps({"status": "error", "error": str(e)})

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

    @mcp.tool()
    async def rotate_item_image(
        item_id: str,
        attachment_id: str,
        degrees: int
    ) -> str:
        """
        Rotates an item's image attachment clockwise.
        degrees: Clockwise rotation amount (e.g. 90, 180, 270).
        """
        return await handle_rotate_image(client, item_id, attachment_id, degrees)

    @mcp.tool()
    async def split_item_from_image(
        id: str,
        extracted_objects: list[dict],
        source: Literal["homebox", "local"] = "homebox",
        attachment_id: str = None
    ) -> str:
        """
        Splits a single inventory item (or local file) into multiple items by providing specific crop boxes for each object.
        Each object in 'extracted_objects' should have: 'name', 'locationId', 'crop_box' ([left, top, right, bottom]), 
        and optionally 'rotation' (any degree), 'description', 'labelIds', 'notes'.
        Deletes the source item/file if at least one item is successfully created.
        """
        return await handle_split_item_from_image(client, id, extracted_objects, source, attachment_id)
