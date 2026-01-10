import base64
import mimetypes
import os
from datetime import UTC, datetime
from typing import Annotated

import anyio
import httpx
from fastmcp import Context, FastMCP
from fastmcp.utilities.types import Image

from ..client import HomeboxClient
from ..guardrails import protect_resource

# --- Tool Handlers ---


async def handle_get_item_image(client: HomeboxClient, id: str) -> Image:
    """Retrieve the primary image for an item."""
    item = await client.request("GET", f"items/{id}")
    attachments = item.get("attachments", [])
    if not attachments:
        raise ValueError(f"No attachments found for item {id}")

    # Use primary attachment or fall back to the first one available
    primary = next((a for a in attachments if a.get("primary")), attachments[0])
    data = await client.request("GET", f"items/{id}/attachments/{primary['id']}", return_bytes=True)

    return Image(data=data, format="png")


async def handle_list_items(
    client: HomeboxClient,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    labels: list[str] | None = None,
    locations: list[str] | None = None,
    parent_ids: list[str] | None = None,
    negate_labels: bool = False,
    only_without_photo: bool = False,
    only_with_photo: bool = False,
    include_archived: bool = False,
    order_by: str | None = None,
) -> dict:
    """Query All Items."""
    params = {}
    if q:
        params["q"] = q
    if page:
        params["page"] = page
    if page_size:
        params["pageSize"] = page_size
    if labels:
        params["labels"] = labels
    if locations:
        params["locations"] = locations
    if parent_ids:
        params["parentIds"] = parent_ids

    # Map boolean flags to the lowercase strings expected by the backend
    params.update(
        {
            "negateLabels": str(negate_labels).lower(),
            "onlyWithoutPhoto": str(only_without_photo).lower(),
            "onlyWithPhoto": str(only_with_photo).lower(),
            "includeArchived": str(include_archived).lower(),
        }
    )

    if order_by:
        params["orderBy"] = order_by

    return await client.list_items(**params)


async def handle_get_item(client: HomeboxClient, id: str) -> dict:
    """Get full details for a specific item by ID."""
    return await client.get_item(id)


async def handle_get_item_link(client: HomeboxClient, query: str) -> str:
    """Searches for an item by name, asset ID, or description and returns its web link."""
    search_query = query
    # Automatically prefix with # if searching for a pure numeric asset ID
    if query.isdigit() or (("-" in query) and query.replace("-", "").isdigit()):
        if not query.startswith("#"):
            search_query = f"#{query}"

    data = await client.request("GET", "items", params={"q": search_query, "pageSize": 5})
    items = data.get("items", [])

    if not items and search_query != query:
        # Retry with original query if asset-search failed
        data = await client.request("GET", "items", params={"q": query, "pageSize": 5})
        items = data.get("items", [])

    if not items:
        return f"No items found matching '{query}'"

    if len(items) == 1:
        item = items[0]
        link = client.get_web_url("item", item["id"])
        return f"✅ Found: {item['name']}\n🔗 Link: {link}"

    output = f"Found {len(items)} matches for '{query}':\n\n"
    for item in items:
        link = client.get_web_url("item", item["id"])
        output += f"- {item['name']} (Asset: {item.get('assetId', 'N/A')})\n  🔗 {link}\n"

    return output


@protect_resource(resource_type="items", action="create")
async def handle_create_item(
    client: HomeboxClient,
    name: str,
    location_id: str,
    description: str | None = None,
    quantity: int = 1,
    parent_id: str | None = None,
    label_ids: list[str] | None = None,
    serial_number: str | None = None,
    model_number: str | None = None,
    manufacturer: str | None = None,
    purchase_price: float | None = None,
    notes: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Creates a new item and performs metadata enrichment."""
    if ctx:
        await ctx.info(f"Creating item '{name}'...")

    create_payload = {
        "name": name,
        "quantity": int(quantity),
        "description": description or "",
        "labelIds": label_ids or [],
        "locationId": location_id,
    }
    if parent_id:
        create_payload["parentId"] = parent_id

    # Phase 1: Create basic item
    created_item = await client.create_item(create_payload)
    item_id = created_item["id"]

    if ctx:
        await ctx.report_progress(50, 100)

    try:
        # Phase 2: Enrich metadata via PUT
        update_payload = created_item.copy()

        # Flatten object references
        if loc := created_item.get("location"):
            update_payload["locationId"] = loc["id"]
        elif location_id:
            update_payload["locationId"] = location_id

        if parent := created_item.get("parent"):
            update_payload["parentId"] = parent["id"]
        elif parent_id:
            update_payload["parentId"] = parent_id

        if labels := created_item.get("labels"):
            update_payload["labelIds"] = [label["id"] for label in labels]
        elif label_ids:
            update_payload["labelIds"] = label_ids

        if notes is not None:
            update_payload["notes"] = notes
        if serial_number is not None:
            update_payload["serialNumber"] = serial_number
        if model_number is not None:
            update_payload["modelNumber"] = model_number
        if manufacturer is not None:
            update_payload["manufacturer"] = manufacturer
        if purchase_price is not None:
            update_payload["purchasePrice"] = str(purchase_price)

        # Initialize required date/string fields if missing
        for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
            if key not in update_payload:
                update_payload[key] = ""
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if key not in update_payload:
                update_payload[key] = "0001-01-01T00:00:00Z"

        final_item = await client.update_item(item_id, update_payload)

        if ctx:
            await ctx.report_progress(100, 100)

        return final_item

    except Exception as e:
        # Rollback
        try:
            await client.delete_item(item_id)
        except Exception:
            pass
        raise e


@protect_resource(resource_type="items", action="update")
async def handle_update_item(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    quantity: int | None = None,
    location_id: str | None = None,
    parent_id: str | None = None,
    label_ids: list[str] | None = None,
    serial_number: str | None = None,
    model_number: str | None = None,
    manufacturer: str | None = None,
    purchase_price: float | None = None,
    notes: str | None = None,
    fields: list[dict] | None = None,
    ctx: Context | None = None,
) -> dict:
    """Update an existing item using merged data via PUT."""
    if ctx:
        await ctx.info(f"Updating item {id}...")

    existing = await client.get_item(id)
    update_payload = existing.copy()

    # Flatten object references
    if loc := existing.get("location"):
        update_payload["locationId"] = loc["id"]
    if parent := existing.get("parent"):
        update_payload["parentId"] = parent["id"]
    if labels := existing.get("labels"):
        update_payload["labelIds"] = [label["id"] for label in labels]

    # Apply updates
    if name is not None:
        update_payload["name"] = name
    if description is not None:
        update_payload["description"] = description
    if notes is not None:
        update_payload["notes"] = notes
    if quantity is not None:
        update_payload["quantity"] = int(quantity)
    if location_id is not None:
        update_payload["locationId"] = location_id
    if parent_id is not None:
        update_payload["parentId"] = parent_id
    if label_ids is not None:
        update_payload["labelIds"] = label_ids
    if serial_number is not None:
        update_payload["serialNumber"] = serial_number
    if model_number is not None:
        update_payload["modelNumber"] = model_number
    if manufacturer is not None:
        update_payload["manufacturer"] = manufacturer
    if purchase_price is not None:
        update_payload["purchasePrice"] = str(purchase_price)
    if fields is not None:
        update_payload["fields"] = fields

    # Preserve existing dates or use zero-dates
    for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
        if key not in update_payload:
            update_payload[key] = existing.get(key, "")
    for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
        if key not in update_payload:
            update_payload[key] = existing.get(key, "0001-01-01T00:00:00Z")

    data = await client.update_item(id, update_payload)

    if ctx:
        await ctx.info(f"Item {id} updated successfully.")

    return data


@protect_resource(resource_type="items", action="update")
async def handle_patch_item(
    client: HomeboxClient,
    id: str,
    location_id: str | None = None,
    quantity: int | None = None,
    label_ids: list[str] | None = None,
) -> dict:
    """Partial update for items via the PATCH endpoint."""
    payload = {}
    if location_id:
        payload["locationId"] = location_id
    if quantity is not None:
        payload["quantity"] = quantity
    if label_ids:
        payload["labelIds"] = label_ids

    return await client.patch_item(id, payload)


@protect_resource(resource_type="items", action="delete")
async def handle_delete_item(client: HomeboxClient, id: str) -> str:
    """Delete an item by ID."""
    await client.delete_item(id)
    return f"Deleted item {id}"


async def handle_get_item_by_asset_id(client: HomeboxClient, id: str) -> dict:
    """Get Item by Asset ID."""
    return await client.get_item_by_asset_id(id)


async def handle_export_items(client: HomeboxClient) -> str:
    """Export all items to CSV format."""
    return await client.export_items()


async def handle_get_item_fields(client: HomeboxClient) -> list[str]:
    """Get all custom field names."""
    return await client.get_item_fields()


async def handle_get_item_field_values(client: HomeboxClient, field: str) -> list[str]:
    """Get all unique values for a specific custom field."""
    return await client.get_item_field_values(field)


async def handle_duplicate_item(
    client: HomeboxClient,
    id: str,
    copy_attachments: bool = False,
    copy_custom_fields: bool = False,
    copy_maintenance: bool = False,
    copy_prefix: str = "Copy of ",
) -> dict:
    """Creates a copy of an item."""
    payload = {
        "copyAttachments": copy_attachments,
        "copyCustomFields": copy_custom_fields,
        "copyMaintenance": copy_maintenance,
        "copyPrefix": copy_prefix,
    }
    return await client.duplicate_item(id, payload)


async def handle_get_item_path(client: HomeboxClient, id: str) -> list[dict]:
    """Get the full breadcrumb path of an item's location."""
    return await client.get_item_path(id)


async def handle_get_item_attachment_token(client: HomeboxClient, id: str, attachment_id: str) -> dict:
    """Get the download details for an item attachment."""
    return await client.get_item_attachment_token(id, attachment_id)


async def handle_delete_item_attachment(client: HomeboxClient, id: str, attachment_id: str) -> str:
    """Permanently delete an item attachment."""
    await client.delete_item_attachment(id, attachment_id)
    return f"Deleted attachment {attachment_id} from item {id}"


async def handle_update_item_attachment(
    client: HomeboxClient,
    id: str,
    attachment_id: str,
    primary: bool | None = None,
    title: str | None = None,
    type: str | None = None,
) -> dict:
    """Update attachment metadata."""
    item = await client.get_item(id)
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        raise ValueError(f"Attachment {attachment_id} not found on item {id}")

    payload = {
        "primary": primary if primary is not None else existing.get("primary", False),
        "title": title if title is not None else existing.get("title", ""),
        "type": type if type is not None else existing.get("type", "attachment"),
    }

    return await client.update_item_attachment(id, attachment_id, payload)


async def handle_get_item_maintenance(client: HomeboxClient, id: str, status: str = "both") -> list[dict]:
    """Get maintenance logs for a specific item."""
    return await client.get_item_maintenance(id, status=status)


async def handle_create_item_maintenance(
    client: HomeboxClient,
    id: str,
    name: str,
    description: str | None = None,
    scheduled_date: str | None = None,
    completed_date: str | None = None,
    cost: float = 0,
) -> dict:
    """Create a maintenance entry for an item."""
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "name": name,
        "cost": str(cost),
        "description": description or "",
        "scheduledDate": scheduled_date or now_iso,
        "completedDate": completed_date or "0001-01-01T00:00:00Z",
    }
    return await client.create_item_maintenance(id, payload)


async def handle_upload_item_attachment(
    client: HomeboxClient, item_id: str, file_path: str, primary: bool = False, attachment_type: str = "photo"
) -> dict:
    """Uploads a file as an item attachment."""
    file_name, mime_type, file_content = "upload", "application/octet-stream", b""

    if file_path.startswith("data:"):
        header, encoded = file_path.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        file_content = base64.b64decode(encoded)
        file_name = f"upload{mimetypes.guess_extension(mime_type) or '.bin'}"

    elif file_path.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(file_path, follow_redirects=True)
            resp.raise_for_status()
            file_content = resp.content
            mime_type = resp.headers.get("content-type", "").split(";")[0] or mime_type
            file_name = os.path.basename(file_path.split("?")[0]) or "upload"
            if "." not in file_name:
                file_name += mimetypes.guess_extension(mime_type) or ""

    else:
        path = anyio.Path(file_path)
        if not await path.exists():
            raise FileNotFoundError(f"File not found at {file_path}")
        file_name = path.name
        mime_type = mimetypes.guess_type(file_path)[0] or mime_type
        file_content = await path.read_bytes()

    files = {"file": (file_name, file_content, mime_type)}
    attachment_meta = {"name": file_name, "type": attachment_type, "primary": "true" if primary else "false"}

    return await client.upload_item_attachment(item_id, files=files, data=attachment_meta)


async def handle_import_items(client: HomeboxClient, file_path: str) -> str:
    """Import items from a CSV file."""
    path = anyio.Path(file_path)
    if not await path.exists():
        raise FileNotFoundError(f"File not found at {file_path}")

    file_content = await path.read_bytes()
    payload_files = {"csv": (path.name, file_content, "text/csv")}
    await client.import_items(files=payload_files)
    return "Items imported successfully."


# --- Registration ---


def register_items_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def list_items(
        q: Annotated[str | None, "Search query"] = None,
        page: Annotated[int, "Page number"] = 1,
        page_size: Annotated[int, "Items per page"] = 50,
        labels: Annotated[list[str] | None, "Label IDs filter"] = None,
        locations: Annotated[list[str] | None, "Location IDs filter"] = None,
        parent_ids: Annotated[list[str] | None, "Parent Item IDs filter"] = None,
        negate_labels: Annotated[bool, "Negate label filter"] = False,
        only_without_photo: Annotated[bool, "Only items without a photo"] = False,
        only_with_photo: Annotated[bool, "Only items with a photo"] = False,
        include_archived: Annotated[bool, "Include archived items"] = False,
        order_by: Annotated[str | None, "Sort order (e.g. 'name', '-name', 'updated_at')"] = None,
    ) -> dict:
        """Query All Items. Supports filtering and pagination."""
        res = await handle_list_items(
            client,
            q=q,
            page=page,
            page_size=page_size,
            labels=labels,
            locations=locations,
            parent_ids=parent_ids,
            negate_labels=negate_labels,
            only_without_photo=only_without_photo,
            only_with_photo=only_with_photo,
            include_archived=include_archived,
            order_by=order_by,
        )
        return res

    @mcp.tool()
    async def list_archived_items(
        q: Annotated[str | None, "Search query"] = None,
        page: Annotated[int, "Page number"] = 1,
        page_size: Annotated[int, "Items per page"] = 50,
    ) -> dict:
        """Query only archived items in the inventory."""
        return await handle_list_items(client, q=q, page=page, page_size=page_size, include_archived=True)

    @mcp.tool()
    async def get_item(id: Annotated[str, "ID of the item"]) -> dict:
        """Get Item details by ID"""
        return await handle_get_item(client, id=id)

    @mcp.tool()
    async def get_item_link(query: Annotated[str, "Asset ID, name, or description"]) -> str:
        """Get the direct link to an item by searching for it."""
        return await handle_get_item_link(client, query=query)

    @mcp.tool()
    async def create_item(
        name: Annotated[str, "Name of the item"],
        location_id: Annotated[str, "ID of the location"],
        description: Annotated[str | None, "Item description"] = None,
        quantity: Annotated[int, "Item quantity"] = 1,
        parent_id: Annotated[str | None, "ID of the parent item"] = None,
        label_ids: Annotated[list[str] | None, "List of label UUIDs"] = None,
        serial_number: Annotated[str | None, "Item serial number"] = None,
        model_number: Annotated[str | None, "Item model number"] = None,
        manufacturer: Annotated[str | None, "Manufacturer name"] = None,
        purchase_price: Annotated[float | None, "Purchase price"] = None,
        notes: Annotated[str | None, "Internal notes"] = None,
        ctx: Context | None = None,
    ) -> dict:
        """Create a new item. Handles complex fields via a two-step process."""
        return await handle_create_item(
            client,
            name=name,
            location_id=location_id,
            description=description,
            quantity=quantity,
            parent_id=parent_id,
            label_ids=label_ids,
            serial_number=serial_number,
            model_number=model_number,
            manufacturer=manufacturer,
            purchase_price=purchase_price,
            notes=notes,
            ctx=ctx,
        )

    @mcp.tool()
    async def update_item(
        id: Annotated[str, "ID of the item"],
        name: Annotated[str | None, "New name for the item"] = None,
        description: Annotated[str | None, "New description for the item"] = None,
        quantity: Annotated[int | None, "New quantity for the item"] = None,
        location_id: Annotated[str | None, "New location ID"] = None,
        parent_id: Annotated[str | None, "New parent item ID"] = None,
        label_ids: Annotated[list[str] | None, "New list of label UUIDs"] = None,
        serial_number: Annotated[str | None, "New serial number"] = None,
        model_number: Annotated[str | None, "New model number"] = None,
        manufacturer: Annotated[str | None, "New manufacturer name"] = None,
        purchase_price: Annotated[float | None, "New purchase price"] = None,
        notes: Annotated[str | None, "New internal notes"] = None,
        fields: Annotated[list[dict] | None, "Custom fields list"] = None,
        ctx: Context | None = None,
    ) -> dict:
        """Update an existing item (replaces existing with merged data)"""
        return await handle_update_item(
            client,
            id=id,
            name=name,
            description=description,
            quantity=quantity,
            location_id=location_id,
            parent_id=parent_id,
            label_ids=label_ids,
            serial_number=serial_number,
            model_number=model_number,
            manufacturer=manufacturer,
            purchase_price=purchase_price,
            notes=notes,
            fields=fields,
            ctx=ctx,
        )

    @mcp.tool()
    async def patch_item(
        id: Annotated[str, "ID of the item"],
        location_id: Annotated[str | None, "ID of the destination location"] = None,
        quantity: Annotated[int | None, "New quantity"] = None,
        label_ids: Annotated[list[str] | None, "New list of label UUIDs"] = None,
    ) -> dict:
        """Update item with PATCH (partial update). Only supports moving, quantity change, and labels."""
        return await handle_patch_item(client, id=id, location_id=location_id, quantity=quantity, label_ids=label_ids)

    @mcp.tool()
    async def delete_item(id: Annotated[str, "ID of the item"]) -> str:
        """Delete an item"""
        return await handle_delete_item(client, id=id)

    @mcp.tool()
    async def get_item_by_asset_id(id: Annotated[str, "Asset ID (e.g. 1234)"]) -> dict:
        """Get Item by Asset ID"""
        return await handle_get_item_by_asset_id(client, id=id)

    @mcp.tool()
    async def export_items() -> str:
        """Export items to CSV"""
        return await handle_export_items(client)

    @mcp.tool
    async def get_item_fields() -> dict:
        """Get all custom field names"""
        res = await handle_get_item_fields(client)
        return {"fields": res}

    @mcp.tool
    async def get_item_field_values(field: Annotated[str, "Custom field name"]) -> dict:
        """Get all custom field values for a specific field name"""
        res = await handle_get_item_field_values(client, field=field)
        return {"values": res}

    @mcp.tool()
    async def duplicate_item(
        id: Annotated[str, "ID of the item to duplicate"],
        copy_attachments: Annotated[bool, "Whether to copy attachments"] = False,
        copy_custom_fields: Annotated[bool, "Whether to copy custom fields"] = False,
        copy_maintenance: Annotated[bool, "Whether to copy maintenance logs"] = False,
        copy_prefix: Annotated[str, "Prefix for the duplicated item name"] = "Copy of ",
    ) -> dict:
        """Duplicate an item"""
        return await handle_duplicate_item(
            client,
            id=id,
            copy_attachments=copy_attachments,
            copy_custom_fields=copy_custom_fields,
            copy_maintenance=copy_maintenance,
            copy_prefix=copy_prefix,
        )

    @mcp.tool
    async def get_item_path(id: Annotated[str, "ID of the item"]) -> dict:
        """Get full path of an item"""
        res = await handle_get_item_path(client, id=id)
        return {"path": res}

    @mcp.tool()
    async def get_item_attachment_token(
        id: Annotated[str, "ID of the item"], attachment_id: Annotated[str, "ID of the attachment"]
    ) -> str:
        """Get the download token for an item attachment"""
        res = await handle_get_item_attachment_token(client, id=id, attachment_id=attachment_id)
        return str(res)

    @mcp.tool()
    async def delete_item_attachment(
        id: Annotated[str, "ID of the item"], attachment_id: Annotated[str, "ID of the attachment"]
    ) -> str:
        """Delete item attachment"""
        return await handle_delete_item_attachment(client, id=id, attachment_id=attachment_id)

    @mcp.tool()
    async def update_item_attachment(
        id: Annotated[str, "ID of the item"],
        attachment_id: Annotated[str, "ID of the attachment"],
        primary: Annotated[bool | None, "Whether this is the primary photo"] = None,
        type: Annotated[str | None, "Type of attachment"] = None,
    ) -> dict:
        """Update item attachment details."""
        return await handle_update_item_attachment(
            client, id=id, attachment_id=attachment_id, primary=primary, type=type
        )

    @mcp.tool
    async def get_item_maintenance(
        id: Annotated[str, "ID of the item"],
        status: Annotated[str, "Filter by status: 'completed', 'scheduled', or 'both'"] = "both",
    ) -> dict:
        """Get maintenance log"""
        res = await handle_get_item_maintenance(client, id=id, status=status)
        return {"maintenance": res}

    @mcp.tool()
    async def create_item_maintenance(
        id: Annotated[str, "ID of the item"],
        name: Annotated[str, "Name of the maintenance entry"],
        description: Annotated[str | None, "Detailed description"] = None,
        scheduled_date: Annotated[str | None, "ISO 8601 scheduled date"] = None,
        completed_date: Annotated[str | None, "ISO 8601 completion date"] = None,
        cost: Annotated[float, "Maintenance cost"] = 0,
    ) -> dict:
        """Create maintenance entry"""
        return await handle_create_item_maintenance(
            client,
            id=id,
            name=name,
            description=description,
            scheduled_date=scheduled_date,
            completed_date=completed_date,
            cost=cost,
        )

    @mcp.tool()
    async def upload_item_attachment(
        item_id: Annotated[str, "ID of the item"],
        file_path: Annotated[str, "Local path, data-uri, or URL of the file"],
        primary: Annotated[bool, "Whether this is the primary photo"] = False,
        attachment_type: Annotated[str, "Type of attachment (e.g. 'photo', 'manual')"] = "photo",
    ) -> dict:
        """Upload an attachment to an item."""
        return await handle_upload_item_attachment(
            client, item_id=item_id, file_path=file_path, primary=primary, attachment_type=attachment_type
        )

    @mcp.tool()
    async def import_items(file_path: Annotated[str, "Local path to the CSV file"]) -> str:
        """Import items from a CSV file."""
        return await handle_import_items(client, file_path=file_path)

    @mcp.tool()
    async def get_item_image(id: Annotated[str, "ID of the item"]) -> Image:
        """Retrieve the primary image for an item."""
        return await handle_get_item_image(client, id=id)
