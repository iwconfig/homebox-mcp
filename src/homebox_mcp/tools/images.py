import os
import io
import logging
from typing import Any, Literal
from PIL import Image as PILImage
from ..client import HomeboxClient
from fastmcp import FastMCP, Context
from fastmcp.utilities.types import Image

logger = logging.getLogger(__name__)

# Inbox directory for local files
# Files placed here will be visible in the get_inbox_queue tool
INBOX_DIR = os.getenv("HOMEBOX_INBOX_DIR", "inbox")

async def handle_get_inbox_queue(client: HomeboxClient) -> list[dict[str, Any]]:
    """
    Returns unified list of items in the Inbox (from Homebox API and local directory).
    Items in the 'Inbox' location in Homebox are merged with files found in INBOX_DIR.
    """
    items = []
    
    # 1. Fetch from Homebox API (Items in 'Inbox' location)
    locations = await client.request("GET", "locations")
    inbox_location = next((loc for loc in locations if loc["name"].lower() == "inbox"), None)
    
    if inbox_location:
        inbox_items = await client.request("GET", "items", params={"locations": [inbox_location["id"]]})
        for item in inbox_items.get("items", []):
            items.append({
                "id": item["id"],
                "name": item["name"],
                "source": "homebox",
                "type": "item",
                "location": item.get("location", {}).get("name", "Inbox"),
                "attachments": item.get("attachments", [])
            })
            
    # 2. Fetch from local directory
    if os.path.exists(INBOX_DIR):
        for filename in os.listdir(INBOX_DIR):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                items.append({
                    "id": filename,
                    "name": filename,
                    "source": "local",
                    "type": "file",
                    "path": os.path.join(INBOX_DIR, filename)
                })
                
    return items

async def handle_get_inbox_image(client: HomeboxClient, id: str, attachment_id: str | None = None) -> Image:
    """
    Retrieve binary image data for an inbox item.
    Supports both local files and Homebox attachments.
    """
    local_path = os.path.join(INBOX_DIR, id)
    if os.path.exists(local_path):
        return Image(path=local_path)
        
    if not attachment_id:
        # Fetch item to find the primary attachment
        item = await client.request("GET", f"items/{id}")
        attachments = item.get("attachments", [])
        if not attachments:
            raise ValueError(f"No attachments found for item {id}")
            
        primary = next((a for a in attachments if a.get("primary")), attachments[0])
        attachment_id = primary["id"]
        
    data = await client.request("GET", f"items/{id}/attachments/{attachment_id}", return_bytes=True)
    return Image(data=data, format="png")

async def _apply_image_ops(image_data: bytes, crop_box: list[int] | None = None, rotation: int | None = None) -> bytes:
    """
    Helper to apply crop and rotation using PIL.
    crop_box: [left, top, right, bottom] in normalized 0-1000 coordinates.
    rotation: degrees counter-clockwise.
    """
    img = PILImage.open(io.BytesIO(image_data))
    
    if crop_box:
        w, h = img.size
        left = int(crop_box[0] * w / 1000)
        top = int(crop_box[1] * h / 1000)
        right = int(crop_box[2] * w / 1000)
        bottom = int(crop_box[3] * h / 1000)
        img = img.crop((left, top, right, bottom))
        
    if rotation:
        # BICUBIC resampling for high quality, expand=True to prevent cropping corners
        img = img.rotate(rotation, resample=PILImage.BICUBIC, expand=True)
        
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()

async def handle_finalize_processed_item(
    client: HomeboxClient,
    id: str,
    name: str,
    locationId: str,
    source: Literal["homebox", "local"] = "homebox",
    description: str | None = None,
    manufacturer: str | None = None,
    modelNumber: str | None = None,
    serialNumber: str | None = None,
    notes: str | None = None,
    labelIds: list[str] | None = None,
    rotation: int | None = None,
    extracted_objects: list[dict[str, Any]] | None = None,
    ctx: Context | None = None
) -> dict[str, Any]:
    """
    Finalizes an item by updating metadata and moving it to a new location.
    Handles single-item updates and multi-object extraction (splitting).
    """
    if extracted_objects:
        if ctx:
            await ctx.info(f"Splitting item {id} into {len(extracted_objects)} items...")
        return await handle_split_item_from_image(client, id, extracted_objects, source=source, ctx=ctx)
        
    if ctx:
        await ctx.info(f"Finalizing item {name} ({id}) from {source}...")
        
    if source == "local":
        local_path = os.path.join(INBOX_DIR, id)
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file {id} not found in inbox")
            
        with open(local_path, "rb") as f:
            file_content = f.read()
            
        if rotation:
            if ctx:
                await ctx.info(f"Applying {rotation} degree rotation...")
            file_content = await _apply_image_ops(file_content, rotation=rotation)
            
        # 1. Create item
        create_payload = {
            "name": name,
            "locationId": locationId,
            "description": description or "",
            "labelIds": labelIds or []
        }
        item = await client.request("POST", "items", json=create_payload)
        new_id = item["id"]
        
        # 2. Upload image
        files = {'file': (f"{name}.png", file_content, "image/png")}
        attach_data = {'name': name, 'type': 'photo', 'primary': 'true'}
        await client.request("POST", f"items/{new_id}/attachments", files=files, data=attach_data)
        
        # 3. Final enrichment
        update_payload = item.copy()
        update_payload.update({
            "manufacturer": manufacturer or "",
            "modelNumber": modelNumber or "",
            "serialNumber": serialNumber or "",
            "notes": notes or "",
            "purchaseTime": "0001-01-01T00:00:00Z",
            "warrantyExpires": "0001-01-01T00:00:00Z"
        })
        await client.request("PUT", f"items/{new_id}", json=update_payload)
        
        # 4. Cleanup
        os.remove(local_path)
        if ctx:
            await ctx.info("Cleanup complete.")
            
        return {"status": "success", "id": new_id, "action": "created_from_local"}
    else:
        # Homebox item update
        if ctx:
            await ctx.info("Updating metadata and location...")
            
        item = await client.request("GET", f"items/{id}")
        update_payload = item.copy()
        
        if "location" in item and item["location"]:
            update_payload["locationId"] = item["location"]["id"]
        if "labels" in item and item["labels"]:
            update_payload["labelIds"] = [label["id"] for label in item["labels"]]
            
        update_payload.update({
            "name": name,
            "locationId": locationId,
            "description": description if description is not None else update_payload.get("description", ""),
            "manufacturer": manufacturer if manufacturer is not None else update_payload.get("manufacturer", ""),
            "modelNumber": modelNumber if modelNumber is not None else update_payload.get("modelNumber", ""),
            "serialNumber": serialNumber if serialNumber is not None else update_payload.get("serialNumber", ""),
            "notes": notes if notes is not None else update_payload.get("notes", ""),
        })
        
        if labelIds is not None:
            update_payload["labelIds"] = labelIds
            
        # Ensure mandatory date fields are present
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if not update_payload.get(key):
                update_payload[key] = "0001-01-01T00:00:00Z"
                
        await client.request("PUT", f"items/{id}", json=update_payload)
        
        if rotation:
            if ctx:
                await ctx.info(f"Rotating image by {rotation} degrees...")
            attachments = item.get("attachments", [])
            if attachments:
                primary = next((a for a in attachments if a.get("primary")), attachments[0])
                await handle_rotate_item_image(client, id, primary["id"], rotation)
                
        if ctx:
            await ctx.info("Update complete.")
            
        return {"status": "success", "id": id, "action": "updated_homebox_item"}

async def handle_crop_item_image(client: HomeboxClient, item_id: str, attachment_id: str, crop_box: list[int]) -> dict[str, Any]:
    """Crops an item's image attachment and replaces the original."""
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    cropped_data = await _apply_image_ops(image_data, crop_box=crop_box)
    
    item = await client.request("GET", f"items/{item_id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        raise ValueError(f"Attachment {attachment_id} not found")
        
    files = {'file': (existing.get("title", "cropped.png"), cropped_data, "image/png")}
    attach_data = {
        'name': existing.get("title", "cropped"),
        'type': existing.get("type", "photo"),
        'primary': 'true' if existing.get("primary") else 'false'
    }
    
    # 1. Upload new cropped version
    await client.request("POST", f"items/{item_id}/attachments", files=files, data=attach_data)
    
    # 2. Delete old version
    await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
    
    return {"status": "success", "action": "cropped"}

async def handle_rotate_item_image(client: HomeboxClient, item_id: str, attachment_id: str, degrees: int) -> dict[str, Any]:
    """Rotates an item's image attachment counter-clockwise and replaces the original."""
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    rotated_data = await _apply_image_ops(image_data, rotation=degrees)
    
    item = await client.request("GET", f"items/{item_id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        raise ValueError(f"Attachment {attachment_id} not found")
        
    files = {'file': (existing.get("title", "rotated.png"), rotated_data, "image/png")}
    attach_data = {
        'name': existing.get("title", "rotated"),
        'type': existing.get("type", "photo"),
        'primary': 'true' if existing.get("primary") else 'false'
    }
    
    # 1. Upload new rotated version
    await client.request("POST", f"items/{item_id}/attachments", files=files, data=attach_data)
    
    # 2. Delete old version
    await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
    
    return {"status": "success", "action": "rotated"}

async def handle_split_item_from_image(
    client: HomeboxClient,
    id: str,
    extracted_objects: list[dict[str, Any]],
    attachment_id: str | None = None,
    source: Literal["homebox", "local"] = "homebox",
    ctx: Context | None = None
) -> dict[str, Any]:
    """
    Splits a single inventory item (or local file) into multiple items by providing crop boxes.
    Deletes the source image/item upon success.
    """
    if ctx:
        await ctx.info(f"Retrieving source image from {source}...")
        
    if source == "local":
        path = os.path.join(INBOX_DIR, id)
        with open(path, "rb") as f:
            source_data = f.read()
    else:
        if not attachment_id:
            item = await client.request("GET", f"items/{id}")
            attachments = item.get("attachments", [])
            primary = next((a for a in attachments if a.get("primary")), attachments[0])
            attachment_id = primary["id"]
        source_data = await client.request("GET", f"items/{id}/attachments/{attachment_id}", return_bytes=True)
        
    results = []
    total = len(extracted_objects)
    
    for i, obj in enumerate(extracted_objects):
        if ctx:
            await ctx.report_progress(i, total, message=f"Extracting {obj['name']}...")
            
        obj_data = await _apply_image_ops(source_data, crop_box=obj.get("crop_box"), rotation=obj.get("rotation"))
        
        # 1. Create item
        create_payload = {
            "name": obj["name"],
            "locationId": obj["locationId"],
            "description": obj.get("description", ""),
            "labelIds": obj.get("labelIds", [])
        }
        new_item = await client.request("POST", "items", json=create_payload)
        new_id = new_item["id"]
        
        # 2. Upload cutout
        files = {'file': (f"{obj['name']}.png", obj_data, "image/png")}
        attach_data = {'name': obj["name"], 'type': 'photo', 'primary': 'true'}
        await client.request("POST", f"items/{new_id}/attachments", files=files, data=attach_data)
        
        # 3. Final enrichment
        update_payload = new_item.copy()
        update_payload.update({
            "notes": obj.get("notes", ""),
            "purchaseTime": "0001-01-01T00:00:00Z",
            "warrantyExpires": "0001-01-01T00:00:00Z"
        })
        await client.request("PUT", f"items/{new_id}", json=update_payload)
        results.append(new_id)
        
    if ctx:
        await ctx.report_progress(total, total, message="All items extracted.")
        
    # Cleanup source
    if source == "local":
        os.remove(os.path.join(INBOX_DIR, id))
    else:
        await client.request("DELETE", f"items/{id}")
        
    return {"status": "success", "created_ids": results, "action": "split"}

def register_vision_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def get_inbox_queue() -> list[dict[str, Any]]:
        """Returns a unified list of items in the Inbox (from Homebox API and local directory) that require processing."""
        return await handle_get_inbox_queue(client)

    @mcp.tool()
    async def get_inbox_image(id: str, attachment_id: str | None = None) -> Image:
        """Retrieve the binary image data for an inbox item (local file or server attachment)."""
        return await handle_get_inbox_image(client, id, attachment_id)

    @mcp.tool()
    async def finalize_processed_item(
        id: str, name: str, locationId: str, source: Literal["homebox", "local"] = "homebox",
        description: str | None = None, manufacturer: str | None = None, modelNumber: str | None = None,
        serialNumber: str | None = None, notes: str | None = None, labelIds: list[str] | None = None,
        rotation: int | None = None, extracted_objects: list[dict[str, Any]] | None = None, ctx: Context = None
    ) -> dict[str, Any]:
        """Finalizes an item by updating metadata and moving it to a new location."""
        return await handle_finalize_processed_item(client, id, name, locationId, source, description, manufacturer, modelNumber, serialNumber, notes, labelIds, rotation, extracted_objects, ctx)

    @mcp.tool()
    async def crop_item_image(item_id: str, attachment_id: str, crop_box: list[int]) -> dict[str, Any]:
        """Crops an item's image attachment to remove background/clutter."""
        return await handle_crop_item_image(client, item_id, attachment_id, crop_box)

    @mcp.tool()
    async def rotate_item_image(item_id: str, attachment_id: str, degrees: int) -> dict[str, Any]:
        """Rotates an item's image attachment counter-clockwise."""
        return await handle_rotate_item_image(client, item_id, attachment_id, degrees)

    @mcp.tool()
    async def split_item_from_image(id: str, extracted_objects: list[dict[str, Any]], attachment_id: str | None = None, source: Literal["homebox", "local"] = "homebox", ctx: Context = None) -> dict[str, Any]:
        """Splits a single inventory item (or local file) into multiple items by providing specific crop boxes for each object."""
        return await handle_split_item_from_image(client, id, extracted_objects, attachment_id, source, ctx)
