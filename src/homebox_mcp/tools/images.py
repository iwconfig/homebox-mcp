import io
import os
from typing import Annotated, Any, Literal

import anyio
from anyio import to_thread
from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image
from PIL import Image as PILImage

from ..client import HomeboxClient

# Inbox directory for local files
INBOX_DIR = os.getenv("HOMEBOX_INBOX_DIR", "inbox")

# --- Tool Handlers ---

async def handle_get_inbox_queue(client: HomeboxClient) -> list[dict[str, Any]]:
    """Returns unified list of items in the Inbox."""
    items = []

    # 1. Fetch from Homebox API
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
    inbox_path = anyio.Path(INBOX_DIR)
    if await inbox_path.exists():
        async for filename in inbox_path.iterdir():
            if filename.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                items.append({
                    "id": filename.name,
                    "name": filename.name,
                    "source": "local",
                    "type": "file",
                    "path": str(filename)
                })

    return items

async def handle_get_inbox_image(client: HomeboxClient, id: str, attachment_id: str | None = None) -> Image:
    """Retrieve binary image data for an inbox item."""
    local_path = anyio.Path(INBOX_DIR) / id
    if await local_path.exists():
        return Image(path=str(local_path))

    if not attachment_id:
        item = await client.request("GET", f"items/{id}")
        attachments = item.get("attachments", [])
        if not attachments:
            raise ValueError(f"No attachments found for item {id}")

        primary = next((a for a in attachments if a.get("primary")), attachments[0])
        attachment_id = primary["id"]

    data = await client.request("GET", f"items/{id}/attachments/{attachment_id}", return_bytes=True)
    return Image(data=data, format="png")

def _sync_image_ops(image_data: bytes, crop_box: list[int] | None = None, rotation: int | None = None) -> bytes:
    """Helper to apply crop and rotation using PIL."""
    img = PILImage.open(io.BytesIO(image_data))

    if crop_box:
        w, h = img.size
        left = int(crop_box[0] * w / 1000)
        top = int(crop_box[1] * h / 1000)
        right = int(crop_box[2] * w / 1000)
        bottom = int(crop_box[3] * h / 1000)
        img = img.crop((left, top, right, bottom))

    if rotation:
        img = img.rotate(rotation, resample=PILImage.BICUBIC, expand=True)

    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()

async def handle_finalize_processed_item(
    client: HomeboxClient,
    id: str,
    name: str,
    location_id: str,
    source: Literal["homebox", "local"] = "homebox",
    description: str | None = None,
    manufacturer: str | None = None,
    model_number: str | None = None,
    serial_number: str | None = None,
    notes: str | None = None,
    label_ids: list[str] | None = None,
    rotation: int | None = None,
    extracted_objects: list[dict[str, Any]] | None = None,
    ctx: Context | None = None
) -> dict[str, Any]:
    """Finalizes an item by updating metadata and moving it to a new location."""
    if extracted_objects:
        return await handle_split_item_from_image(client, id, extracted_objects, source=source, ctx=ctx)

    if source == "local":
        local_path = anyio.Path(INBOX_DIR) / id
        if not await local_path.exists():
            raise FileNotFoundError(f"Local file {id} not found in inbox")

        file_content = await local_path.read_bytes()

        if rotation:
            file_content = await to_thread.run_sync(_sync_image_ops, file_content, None, rotation)

        # 1. Create item
        create_payload = {
            "name": name,
            "locationId": location_id,
            "description": description or "",
            "labelIds": label_ids or []
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
            "modelNumber": model_number or "",
            "serialNumber": serial_number or "",
            "notes": notes or "",
            "purchaseTime": "0001-01-01T00:00:00Z",
            "warrantyExpires": "0001-01-01T00:00:00Z"
        })
        await client.request("PUT", f"items/{new_id}", json=update_payload)

        # 4. Cleanup
        await local_path.unlink()
        return {"status": "success", "id": new_id, "action": "created_from_local"}
    else:
        # Homebox item update
        item = await client.request("GET", f"items/{id}")
        update_payload = item.copy()

        if "location" in item and item["location"]:
            update_payload["locationId"] = item["location"]["id"]
        if "labels" in item and item["labels"]:
            update_payload["labelIds"] = [label["id"] for label in item["labels"]]

        update_payload.update({
            "name": name,
            "locationId": location_id,
            "description": description if description is not None else update_payload.get("description", ""),
            "manufacturer": manufacturer if manufacturer is not None else update_payload.get("manufacturer", ""),
            "modelNumber": model_number if model_number is not None else update_payload.get("modelNumber", ""),
            "serialNumber": serial_number if serial_number is not None else update_payload.get("serialNumber", ""),
            "notes": notes if notes is not None else update_payload.get("notes", ""),
        })

        if label_ids is not None:
            update_payload["labelIds"] = label_ids

        # Ensure mandatory date fields are present
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if not update_payload.get(key):
                update_payload[key] = "0001-01-01T00:00:00Z"

        await client.request("PUT", f"items/{id}", json=update_payload)

        if rotation:
            attachments = item.get("attachments", [])
            if attachments:
                primary = next((a for a in attachments if a.get("primary")), attachments[0])
                await handle_rotate_item_image(client, id, primary["id"], rotation)

        return {"status": "success", "id": id, "action": "updated_homebox_item"}

async def handle_crop_item_image(
    client: HomeboxClient,
    item_id: str,
    attachment_id: str,
    crop_box: list[int]
) -> dict[str, Any]:
    """Crops an item's image attachment and replaces the original."""
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    cropped_data = await to_thread.run_sync(_sync_image_ops, image_data, crop_box, None)

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

async def handle_rotate_item_image(
    client: HomeboxClient,
    item_id: str,
    attachment_id: str,
    degrees: int
) -> dict[str, Any]:
    """Rotates an item's image attachment and replaces the original."""
    image_data = await client.request("GET", f"items/{item_id}/attachments/{attachment_id}", return_bytes=True)
    rotated_data = await to_thread.run_sync(_sync_image_ops, image_data, None, degrees)

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
    """Splits an item into multiple items by providing crop boxes."""
    if source == "local":
        path = anyio.Path(INBOX_DIR) / id
        source_data = await path.read_bytes()
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
            await ctx.report_progress(i, total)

        obj_data = await to_thread.run_sync(
            _sync_image_ops,
            source_data,
            obj.get("crop_box"),
            obj.get("rotation")
        )

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
        await ctx.report_progress(total, total)

    # Cleanup source
    if source == "local":
        path = anyio.Path(INBOX_DIR) / id
        await path.unlink()
    else:
        await client.request("DELETE", f"items/{id}")

    return {"status": "success", "created_ids": results, "action": "split"}

# --- Registration ---

def register_vision_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def get_inbox_queue() -> dict:
        """Returns a unified list of items in the Inbox that require processing."""
        res = await handle_get_inbox_queue(client)
        return {"queue": res}

    @mcp.tool()
    async def get_inbox_image(
        id: Annotated[str, "ID of the item or local file name"],
        attachment_id: Annotated[str | None, "Optional attachment ID for Homebox items"] = None
    ) -> Image:
        """Retrieve the binary image data for an inbox item."""
        return await handle_get_inbox_image(client, id=id, attachment_id=attachment_id)

    @mcp.tool()
    async def finalize_processed_item(
        id: Annotated[str, "ID of the item or local file name"],
        name: Annotated[str, "Final name for the item"],
        location_id: Annotated[str, "Final location ID"],
        source: Annotated[Literal["homebox", "local"], "Source of the item"] = "homebox",
        description: Annotated[str | None, "Item description"] = None,
        manufacturer: Annotated[str | None, "Manufacturer name"] = None,
        model_number: Annotated[str | None, "Model number"] = None,
        serial_number: Annotated[str | None, "Serial number"] = None,
        notes: Annotated[str | None, "Internal notes"] = None,
        label_ids: Annotated[list[str] | None, "List of label UUIDs"] = None,
        rotation: Annotated[int | None, "Rotation to apply (counter-clockwise)"] = None,
        extracted_objects: Annotated[list[dict[str, Any]] | None, "List of objects to extract (splitting)"] = None,
        ctx: Context | None = None
    ) -> dict[str, Any]:
        """Finalizes an item by updating metadata and moving it to a new location."""
        return await handle_finalize_processed_item(
            client, id=id, name=name, location_id=location_id, source=source,
            description=description, manufacturer=manufacturer, model_number=model_number,
            serial_number=serial_number, notes=notes, label_ids=label_ids,
            rotation=rotation, extracted_objects=extracted_objects, ctx=ctx
        )

    @mcp.tool()
    async def crop_item_image(
        item_id: Annotated[str, "ID of the item"],
        attachment_id: Annotated[str, "ID of the attachment to crop"],
        crop_box: Annotated[list[int], "Crop box [left, top, right, bottom] in 0-1000 scale"]
    ) -> dict[str, Any]:
        """Crops an item's image attachment to remove background/clutter."""
        return await handle_crop_item_image(client, item_id=item_id, attachment_id=attachment_id, crop_box=crop_box)

    @mcp.tool()
    async def rotate_item_image(
        item_id: Annotated[str, "ID of the item"],
        attachment_id: Annotated[str, "ID of the attachment to rotate"],
        degrees: Annotated[int, "Degrees to rotate counter-clockwise"]
    ) -> dict[str, Any]:
        """Rotates an item's image attachment counter-clockwise."""
        return await handle_rotate_item_image(client, item_id=item_id, attachment_id=attachment_id, degrees=degrees)

    @mcp.tool()
    async def split_item_from_image(
        id: Annotated[str, "ID of the item or local file name"],
        extracted_objects: Annotated[list[dict[str, Any]], "List of objects with names, locations, and crop boxes"],
        attachment_id: Annotated[str | None, "Optional attachment ID"] = None,
        source: Annotated[Literal["homebox", "local"], "Source of the item"] = "homebox",
        ctx: Context | None = None
    ) -> dict[str, Any]:
        """Splits a single inventory item (or local file) into multiple items."""
        return await handle_split_item_from_image(
            client, id=id, extracted_objects=extracted_objects,
            attachment_id=attachment_id, source=source, ctx=ctx
        )
