import os
import json
import base64
import io
import logging
import mimetypes
from typing import Optional, List, Dict, Any, Literal
from PIL import Image as PILImage
from ..client import HomeboxClient
from ..guardrails import protect_resource
from fastmcp import FastMCP, Context
from fastmcp.utilities.types import Image

logger = logging.getLogger(__name__)

# Inbox directory for local files
INBOX_DIR = os.getenv("HOMEBOX_INBOX_DIR", "inbox")

async def handle_get_inbox_queue(client: HomeboxClient) -> List[Dict[str, Any]]:
    """Returns unified list of items in the Inbox (from Homebox API and local directory)."""
    items = []
    
    # 1. Fetch from Homebox API (Items in 'Inbox' location)
    # We search for location named 'Inbox'
    locations = await client.request("GET", "locations", params={"q": "Inbox"})
    inbox_location = next((l for l in locations.get("items", []) if l["name"].lower() == "inbox"), None)
    
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

async def handle_get_inbox_image(client: HomeboxClient, id: str, attachment_id: Optional[str] = None) -> Image:
    """Retrieve binary image data for an inbox item."""
    # Check if it's a local file
    local_path = os.path.join(INBOX_DIR, id)
    if os.path.exists(local_path):
        return Image(path=local_path)
    
    # Otherwise, it's a Homebox item
    if not attachment_id:
        item = await client.request("GET", f"items/{id}")
        attachments = item.get("attachments", [])
        if not attachments:
            raise ValueError(f"No attachments found for item {id}")
        # Use primary or first photo
        primary = next((a for a in attachments if a.get("primary")), attachments[0])
        attachment_id = primary["id"]
        
    data = await client.request("GET", f"items/{id}/attachments/{attachment_id}", return_bytes=True)
    return Image(data=data, format="png") # Assuming png for now or detect from content

async def _apply_image_ops(image_data: bytes, crop_box: Optional[List[int]] = None, rotation: Optional[int] = None) -> bytes:
    """Helper to apply crop and rotation using PIL."""
    img = PILImage.open(io.BytesIO(image_data))
    
    if crop_box:
        # crop_box: [left, top, right, bottom] in normalized 0-1000 coordinates
        w, h = img.size
        left = int(crop_box[0] * w / 1000)
        top = int(crop_box[1] * h / 1000)
        right = int(crop_box[2] * w / 1000)
        bottom = int(crop_box[3] * h / 1000)
        img = img.crop((left, top, right, bottom))
        
    if rotation:
        # rotation: Counter-Clockwise (CCW)
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
    description: Optional[str] = None,
    manufacturer: Optional[str] = None,
    modelNumber: Optional[str] = None,
    serialNumber: Optional[str] = None,
    notes: Optional[str] = None,
    labelIds: Optional[List[str]] = None,
    rotation: Optional[int] = None,
    extracted_objects: Optional[List[Dict[str, Any]]] = None,
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Finalizes an item by updating metadata and moving it to a new location."""
    
    if extracted_objects:
        # Special case: Splitting into multiple objects
        if ctx: await ctx.info(f"Splitting item {id} into {len(extracted_objects)} items...")
        return await handle_split_item_from_image(client, id, extracted_objects, source=source, ctx=ctx)

    if ctx: await ctx.info(f"Finalizing item {name} ({id}) from {source}...")

    if source == "local":
        # 1. Upload to Homebox first
        local_path = os.path.join(INBOX_DIR, id)
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file {id} not found in inbox")
            
        with open(local_path, "rb") as f:
            file_content = f.read()
            
        if rotation:
            if ctx: await ctx.info(f"Applying {rotation} degree rotation...")
            file_content = await _apply_image_ops(file_content, rotation=rotation)
            
        # Create item
        if ctx: await ctx.info("Creating item in Homebox...")
        create_payload = {
            "name": name,
            "locationId": locationId,
            "description": description or "",
            "labelIds": labelIds or []
        }
        item = await client.request("POST", "items", json=create_payload)
        new_id = item["id"]
        
        # Upload attachment
        if ctx: await ctx.info("Uploading image attachment...")
        files = {'file': (name + ".png", file_content, "image/png")}
        data = {'name': name, 'type': 'photo', 'primary': 'true'}
        await client.request("POST", f"items/{new_id}/attachments", files=files, data=data)
        
        # Update other metadata
        if ctx: await ctx.info("Enriching metadata...")
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
        
        # Delete local file
        os.remove(local_path)
        if ctx: await ctx.info("Cleanup complete.")
        return {"status": "success", "id": new_id, "action": "created_from_local"}

    else:
        # Source is homebox
        # 1. Update item metadata and location
        if ctx: await ctx.info("Updating metadata and location...")
        item = await client.request("GET", f"items/{id}")
        update_payload = item.copy()
        
        # Handle objects returned by API vs IDs expected by PUT
        if "location" in item and item["location"]:
            update_payload["locationId"] = item["location"]["id"]
        if "labels" in item and item["labels"]:
            update_payload["labelIds"] = [l["id"] for l in item["labels"]]
            
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
            
        # Ensure dates are set
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if not update_payload.get(key):
                update_payload[key] = "0001-01-01T00:00:00Z"

        await client.request("PUT", f"items/{id}", json=update_payload)
        
        # 2. Handle rotation if needed
        if rotation:
            if ctx: await ctx.info(f"Rotating image by {rotation} degrees...")
            attachments = item.get("attachments", [])
            if attachments:
                primary = next((a for a in attachments if a.get("primary")), attachments[0])
                await handle_rotate_item_image(client, id, primary["id"], rotation)
                
        if ctx: await ctx.info("Update complete.")
        return {"status": "success", "id": id, "action": "updated_homebox_item"}

async def handle_crop_item_image(client: HomeboxClient, item_id: str, attachment_id: str, crop_box: List[int]) -> Dict[str, Any]:
    """Crops an item's image attachment."""
    # 1. Download
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    
    # 2. Crop
    cropped_data = await _apply_image_ops(image_data, crop_box=crop_box)
    
    # 3. Get attachment details to preserve them
    item = await client.request("GET", f"items/{item_id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        raise ValueError(f"Attachment {attachment_id} not found")
        
    # 4. Upload as new and delete old
    files = {'file': (existing.get("title", "cropped.png"), cropped_data, "image/png")}
    data = {'name': existing.get("title", "cropped"), 'type': existing.get("type", "photo"), 'primary': 'true' if existing.get("primary") else 'false'}
    await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
    await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
    
    return {"status": "success", "action": "cropped"}

async def handle_rotate_item_image(client: HomeboxClient, item_id: str, attachment_id: str, degrees: int) -> Dict[str, Any]:
    """Rotates an item's image attachment counter-clockwise."""
    # 1. Download
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    
    # 2. Rotate
    rotated_data = await _apply_image_ops(image_data, rotation=degrees)
    
    # 3. Get attachment details
    item = await client.request("GET", f"items/{item_id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    
    # 4. Upload new and delete old
    files = {'file': (existing.get("title", "rotated.png"), rotated_data, "image/png")}
    data = {'name': existing.get("title", "rotated"), 'type': existing.get("type", "photo"), 'primary': 'true' if existing.get("primary") else 'false'}
    await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
    await client.request("DELETE", f"items/{item_id}/attachments/{attachment_id}")
    
    return {"status": "success", "action": "rotated"}

async def handle_split_item_from_image(
    client: HomeboxClient,
    id: str,
    extracted_objects: List[Dict[str, Any]],
    attachment_id: Optional[str] = None,
    source: Literal["homebox", "local"] = "homebox",
    ctx: Optional[Context] = None
) -> Dict[str, Any]:
    """Splits a single inventory item (or local file) into multiple items."""
    
    # 1. Get source image data
    if ctx: await ctx.info(f"Retrieving source image from {source}...")
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
        # obj has: name, locationId, crop_box, rotation, description, labelIds, notes
        if ctx: await ctx.report_progress(i, total, message=f"Extracting {obj['name']}...")
        
        crop_box = obj.get("crop_box")
        rotation = obj.get("rotation")
        
        # Apply ops
        obj_data = await _apply_image_ops(source_data, crop_box=crop_box, rotation=rotation)
        
        # Create item
        create_payload = {
            "name": obj["name"],
            "locationId": obj["locationId"],
            "description": obj.get("description", ""),
            "labelIds": obj.get("labelIds", [])
        }
        new_item = await client.request("POST", "items", json=create_payload)
        new_id = new_item["id"]
        
        # Upload attachment
        files = {'file': (obj["name"] + ".png", obj_data, "image/png")}
        data = {'name': obj["name"], 'type': 'photo', 'primary': 'true'}
        await client.request("POST", f"items/{new_id}/attachments", files=files, data=data)
        
        # Update metadata
        update_payload = new_item.copy()
        update_payload.update({
            "notes": obj.get("notes", ""),
            "purchaseTime": "0001-01-01T00:00:00Z",
            "warrantyExpires": "0001-01-01T00:00:00Z"
        })
        await client.request("PUT", f"items/{new_id}", json=update_payload)
        results.append(new_id)

    if ctx: await ctx.report_progress(total, total, message="All items extracted.")

    # Cleanup source
    if source == "local":
        os.remove(os.path.join(INBOX_DIR, id))
    else:
        await client.request("DELETE", f"items/{id}")
        
    return {"status": "success", "created_ids": results, "action": "split"}


# --- Registration ---

def register_vision_tools(mcp: FastMCP, client: HomeboxClient):
    
    @mcp.tool()
    async def get_inbox_queue() -> List[Dict[str, Any]]:
        """Returns a unified list of items in the Inbox (from Homebox API and local directory) that require processing."""
        return await handle_get_inbox_queue(client)

    @mcp.tool()
    async def get_inbox_image(id: str, attachment_id: Optional[str] = None) -> Image:
        """Retrieve the binary image data for an inbox item (local file or server attachment)."""
        return await handle_get_inbox_image(client, id, attachment_id)

    @mcp.tool()
    async def finalize_processed_item(
        id: str,
        name: str,
        locationId: str,
        source: Literal["homebox", "local"] = "homebox",
        description: Optional[str] = None,
        manufacturer: Optional[str] = None,
        modelNumber: Optional[str] = None,
        serialNumber: Optional[str] = None,
        notes: Optional[str] = None,
        labelIds: Optional[List[str]] = None,
        rotation: Optional[int] = None,
        extracted_objects: Optional[List[Dict[str, Any]]] = None,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Finalizes an item by updating metadata and moving it to a new location.
        If source is 'local', it handles the initial upload to Homebox.
        Supports optional rotation (any degree, e.g. 15, -90) and extracting multiple objects via crop boxes.
        If extracted_objects is used, the source item is deleted.
        Returns a JSON object with the result status and actions taken.
        """
        return await handle_finalize_processed_item(
            client, id, name, locationId, source, description, manufacturer,
            modelNumber, serialNumber, notes, labelIds, rotation, extracted_objects, ctx
        )

    @mcp.tool()
    async def crop_item_image(item_id: str, attachment_id: str, crop_box: List[int]) -> Dict[str, Any]:
        """
        Crops an item's image attachment to remove background/clutter.
        Replaces the existing attachment with the cropped version.
        crop_box: [left, top, right, bottom] in normalized 0-1000 coordinates.
        """
        return await handle_crop_item_image(client, item_id, attachment_id, crop_box)

    @mcp.tool()
    async def rotate_item_image(item_id: str, attachment_id: str, degrees: int) -> Dict[str, Any]:
        """
        Rotates an item's image attachment counter-clockwise.
        degrees: Counter-Clockwise (CCW) rotation amount (e.g. 90, 180, 270).
        """
        return await handle_rotate_item_image(client, item_id, attachment_id, degrees)

    @mcp.tool()
    async def split_item_from_image(
        id: str,
        extracted_objects: List[Dict[str, Any]],
        attachment_id: Optional[str] = None,
        source: Literal["homebox", "local"] = "homebox",
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Splits a single inventory item (or local file) into multiple items by providing specific crop boxes for each object.
        Each object in 'extracted_objects' should have: 'name', 'locationId', 'crop_box' ([left, top, right, bottom] in normalized 0-1000 coordinates), 
        and optionally 'rotation' (any degree CCW), 'description', 'labelIds', 'notes'.
        Deletes the source item/file if at least one item is successfully created.
        """
        return await handle_split_item_from_image(client, id, extracted_objects, attachment_id, source, ctx)
