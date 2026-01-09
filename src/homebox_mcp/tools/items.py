import json
import os
import mimetypes
import httpx
import base64
from datetime import datetime, timezone
from typing import Annotated
from pydantic import Field
from ..client import HomeboxClient
from ..guardrails import protect_resource
from fastmcp import FastMCP, Context
from fastmcp.utilities.types import Image
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform

# --- Tool Handlers ---

async def handle_get_item_image(client: HomeboxClient, id: str) -> Image:
    """Retrieve the primary image for an item."""
    item = await client.request("GET", f"items/{id}")
    attachments = item.get("attachments", [])
    if not attachments:
        raise ValueError(f"No attachments found for item {id}")
    primary = next((a for a in attachments if a.get("primary")), attachments[0])
    data = await client.request("GET", f"items/{id}/attachments/{primary['id']}", return_bytes=True)
    return Image(data=data, format="png")

async def handle_list_items(
    client: HomeboxClient,
    q: str | None = None,
    page: int = 1,
    pageSize: int = 50,
    labels: list[str] | None = None,
    locations: list[str] | None = None,
    parentIds: list[str] | None = None,
    negateLabels: bool = False,
    onlyWithoutPhoto: bool = False,
    onlyWithPhoto: bool = False,
    includeArchived: bool = False,
    orderBy: str | None = None
) -> str:
    params = {}
    if q:
        params["q"] = q
    if page:
        params["page"] = page
    if pageSize:
        params["pageSize"] = pageSize
    if labels:
        params["labels"] = labels
    if locations:
        params["locations"] = locations
    if parentIds:
        params["parentIds"] = parentIds
    params.update({
        "negateLabels": str(negateLabels).lower(),
        "onlyWithoutPhoto": str(onlyWithoutPhoto).lower(),
        "onlyWithPhoto": str(onlyWithPhoto).lower(),
        "includeArchived": str(includeArchived).lower()
    })
    if orderBy:
        params["orderBy"] = orderBy
    data = await client.request("GET", "items", params=params)
    items = data.get("items", [])
    output = f"Found {data.get('total', len(items))} items (Page {data.get('page', 1)}/{data.get('totalPages', '?')})\n\n"
    for item in items:
        link = client.get_web_url("item", item["id"])
        output += f"- [{item.get('name')}]({link}) (ID: {item.get('id')})\n"
        if loc := item.get("location"):
            output += f"  Location: {loc.get('name')}\n"
        if qty := item.get("quantity"):
            output += f"  Qty: {qty}\n"
    return output

async def handle_get_item(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"items/{id}")
    link = client.get_web_url("item", data["id"])
    return f"Item: {data.get('name')}\nLink: {link}\n\n{json.dumps(data, indent=2)}"

async def handle_get_item_link(client: HomeboxClient, query: str) -> str:
    search_query = query
    if query.isdigit() or (("-" in query) and query.replace("-", "").isdigit()):
        if not query.startswith("#"):
            search_query = f"#{query}"
    data = await client.request("GET", "items", params={"q": search_query, "pageSize": 5})
    items = data.get("items", [])
    if not items and search_query != query:
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
    locationId: str,
    description: str | None = None,
    quantity: int = 1,
    parentId: str | None = None,
    labelIds: list[str] | None = None,
    serialNumber: str | None = None,
    modelNumber: str | None = None,
    manufacturer: str | None = None,
    purchasePrice: float | None = None,
    notes: str | None = None,
    ctx: Context | None = None
) -> str:
    if ctx:
        await ctx.info(f"Creating item '{name}'...")
    create_payload = {
        "name": name,
        "quantity": int(quantity),
        "description": description or "",
        "labelIds": labelIds or [],
        "locationId": locationId
    }
    if parentId:
        create_payload["parentId"] = parentId
    created_item = await client.request("POST", "items", json=create_payload)
    item_id = created_item["id"]
    if ctx:
        await ctx.report_progress(50, 100, message="Item created, enriching metadata...")
    try:
        update_payload = created_item.copy()
        if loc := created_item.get("location"):
            update_payload["locationId"] = loc["id"]
        elif locationId:
            update_payload["locationId"] = locationId
        if parent := created_item.get("parent"):
            update_payload["parentId"] = parent["id"]
        elif parentId:
            update_payload["parentId"] = parentId
        if labels := created_item.get("labels"):
            update_payload["labelIds"] = [label["id"] for label in labels]
        elif labelIds:
            update_payload["labelIds"] = labelIds
        if notes is not None:
            update_payload["notes"] = notes
        if serialNumber is not None:
            update_payload["serialNumber"] = serialNumber
        if modelNumber is not None:
            update_payload["modelNumber"] = modelNumber
        if manufacturer is not None:
            update_payload["manufacturer"] = manufacturer
        if purchasePrice is not None:
            update_payload["purchasePrice"] = str(purchasePrice)
        for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
            if key not in update_payload:
                update_payload[key] = ""
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if key not in update_payload:
                update_payload[key] = "0001-01-01T00:00:00Z"
        final_item = await client.request("PUT", f"items/{item_id}", json=update_payload)
        if ctx:
            await ctx.report_progress(100, 100, message="Item enriched successfully.")
        return f"Created and Enriched Item: {json.dumps(final_item, indent=2)}"
    except Exception as e:
        try:
            await client.request("DELETE", f"items/{item_id}")
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
    locationId: str | None = None,
    parentId: str | None = None,
    labelIds: list[str] | None = None,
    serialNumber: str | None = None,
    modelNumber: str | None = None,
    manufacturer: str | None = None,
    purchasePrice: float | None = None,
    notes: str | None = None,
    fields: list[dict] | None = None,
    ctx: Context | None = None
) -> str:
    if ctx:
        await ctx.info(f"Updating item {id}...")
    existing = await client.request("GET", f"items/{id}")
    update_payload = existing.copy()
    if loc := existing.get("location"):
        update_payload["locationId"] = loc["id"]
    if parent := existing.get("parent"):
        update_payload["parentId"] = parent["id"]
    if labels := existing.get("labels"):
        update_payload["labelIds"] = [label["id"] for label in labels]
    if name is not None:
        update_payload["name"] = name
    if description is not None:
        update_payload["description"] = description
    if notes is not None:
        update_payload["notes"] = notes
    if quantity is not None:
        update_payload["quantity"] = int(quantity)
    if locationId is not None:
        update_payload["locationId"] = locationId
    if parentId is not None:
        update_payload["parentId"] = parentId
    if labelIds is not None:
        update_payload["labelIds"] = labelIds
    if serialNumber is not None:
        update_payload["serialNumber"] = serialNumber
    if modelNumber is not None:
        update_payload["modelNumber"] = modelNumber
    if manufacturer is not None:
        update_payload["manufacturer"] = manufacturer
    if purchasePrice is not None:
        update_payload["purchasePrice"] = str(purchasePrice)
    if fields is not None:
        update_payload["fields"] = fields
    for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
        if key not in update_payload:
            update_payload[key] = existing.get(key, "")
    for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
        if key not in update_payload:
            update_payload[key] = existing.get(key, "0001-01-01T00:00:00Z")
    data = await client.request("PUT", f"items/{id}", json=update_payload)
    if ctx:
        await ctx.info(f"Item {id} updated successfully.")
    return f"Updated Item: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="items", action="update")
async def handle_patch_item(client: HomeboxClient, id: str, locationId: str | None = None, quantity: int | None = None, labelIds: list[str] | None = None) -> str:
    payload = {}
    if locationId:
        payload["locationId"] = locationId
    if quantity is not None:
        payload["quantity"] = quantity
    if labelIds:
        payload["labelIds"] = labelIds
    data = await client.request("PATCH", f"items/{id}", json=payload)
    return f"Patched Item: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="items", action="delete")
async def handle_delete_item(client: HomeboxClient, id: str) -> str:
    await client.request("DELETE", f"items/{id}")
    return f"Deleted item {id}"

async def handle_get_item_by_asset_id(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"assets/{id}")
    return json.dumps(data, indent=2)

async def handle_export_items(client: HomeboxClient) -> str:
    return await client.request("GET", "items/export")

async def handle_get_item_fields(client: HomeboxClient) -> str:
    data = await client.request("GET", "items/fields")
    return json.dumps(data, indent=2)

async def handle_get_item_field_values(client: HomeboxClient, field: str) -> str:
    try:
        data = await client.request("GET", "items/fields/values", params={"field": field})
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching item field values for '{field}': {str(e)}"

async def handle_duplicate_item(client: HomeboxClient, id: str, copyAttachments: bool = False, copyCustomFields: bool = False, copyMaintenance: bool = False, copyPrefix: str = "Copy of ") -> str:
    payload = {"copyAttachments": copyAttachments, "copyCustomFields": copyCustomFields, "copyMaintenance": copyMaintenance, "copyPrefix": copyPrefix}
    data = await client.request("POST", f"items/{id}/duplicate", json=payload)
    return f"Duplicated Item: {json.dumps(data, indent=2)}"

async def handle_get_item_path(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"items/{id}/path")
    return json.dumps(data, indent=2)

async def handle_get_item_attachment_token(client: HomeboxClient, id: str, attachment_id: str) -> str:
    data = await client.request("GET", f"items/{id}/attachments/{attachment_id}")
    return json.dumps(data, indent=2)

async def handle_delete_item_attachment(client: HomeboxClient, id: str, attachment_id: str) -> str:
    await client.request("DELETE", f"items/{id}/attachments/{attachment_id}")
    return "Deleted attachment"

async def handle_update_item_attachment(client: HomeboxClient, id: str, attachment_id: str, primary: bool | None = None, title: str | None = None, type: str | None = None) -> str:
    item = await client.request("GET", f"items/{id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        return f"Error: Attachment {attachment_id} not found on item {id}"
    payload = {"primary": primary if primary is not None else existing.get("primary", False), "title": title if title is not None else existing.get("title", ""), "type": type if type is not None else existing.get("type", "attachment")}
    data = await client.request("PUT", f"items/{id}/attachments/{attachment_id}", json=payload)
    return f"Updated Attachment: {json.dumps(data, indent=2)}"

async def handle_get_item_maintenance(client: HomeboxClient, id: str, status: str = "both") -> str:
    data = await client.request("GET", f"items/{id}/maintenance", params={"status": status})
    return json.dumps(data, indent=2)

async def handle_create_item_maintenance(client: HomeboxClient, id: str, name: str, description: str | None = None, scheduledDate: str | None = None, completedDate: str | None = None, cost: float = 0) -> str:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {"name": name, "cost": str(cost), "description": description or "", "scheduledDate": scheduledDate or now_iso, "completedDate": completedDate or "0001-01-01T00:00:00Z"}
    try:
        data = await client.request("POST", f"items/{id}/maintenance", json=payload)
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error creating maintenance entry: {str(e)}"

async def handle_upload_item_attachment(
    client: HomeboxClient,
    item_id: str,
    file_path: str,
    primary: bool = False,
    attachment_type: str = "photo"
) -> str:
    file_name, mime_type, file_content = "upload", 'application/octet-stream', b""
    if file_path.startswith("data:"):
        try:
            header, encoded = file_path.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            file_content = base64.b64decode(encoded)
            file_name = f"upload{mimetypes.guess_extension(mime_type) or '.bin'}"
        except Exception as e:
            return f"Error: Failed to decode base64 data: {str(e)}"
    elif file_path.startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(file_path, follow_redirects=True)
                resp.raise_for_status()
                file_content = resp.content
                mime_type = resp.headers.get("content-type", "").split(";")[0] or mime_type
                file_name = os.path.basename(file_path.split("?")[0]) or "upload"
                if "." not in file_name:
                    file_name += (mimetypes.guess_extension(mime_type) or "")
        except Exception as e:
            return f"Error: Failed to download from URL: {str(e)}"
    else:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        file_name, mime_type = os.path.basename(file_path), mimetypes.guess_type(file_path)[0] or mime_type
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            return f"Error: Failed to read local file: {str(e)}"
    files = {'file': (file_name, file_content, mime_type)}
    try:
        result = await client.request("POST", f"items/{item_id}/attachments", files=files, data={'name': file_name, 'type': attachment_type, 'primary': 'true' if primary else 'false'})
        return f"Attachment uploaded successfully: {json.dumps(result, indent=2)}"
    except Exception as e:
        return f"Failed to upload attachment: {str(e)}"

async def handle_import_items(client: HomeboxClient, file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    with open(file_path, 'rb') as f:
        file_content = f.read()
    try:
        await client.request("POST", "items/import", files={'csv': (os.path.basename(file_path), file_content, 'text/csv')})
        return "Items imported successfully."
    except Exception as e:
        return f"Failed to import items: {str(e)}"

# --- Registration ---

def register_items_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def list_items(
        q: Annotated[str | None, Field(description="Search string")] = None,
        page: Annotated[int, Field(description="Page number", ge=1)] = 1,
        pageSize: Annotated[int, Field(description="Items per page", ge=1, le=100)] = 50,
        labels: Annotated[list[str] | None, Field(description="Label IDs filter")] = None,
        locations: Annotated[list[str] | None, Field(description="Location IDs filter")] = None,
        parentIds: Annotated[list[str] | None, Field(description="Parent Item IDs filter")] = None,
        negateLabels: Annotated[bool, Field(description="Negate label filter")] = False,
        onlyWithoutPhoto: Annotated[bool, Field(description="Only items without a photo")] = False,
        onlyWithPhoto: Annotated[bool, Field(description="Only items with a photo")] = False,
        includeArchived: Annotated[bool, Field(description="Include archived items")] = False,
        orderBy: Annotated[str | None, Field(description="Sort order (e.g. 'name', '-name', 'updated_at')")] = None
    ) -> str:
        """Query All Items. Supports filtering and pagination."""
        return await handle_list_items(client, q, page, pageSize, labels, locations, parentIds, negateLabels, onlyWithoutPhoto, onlyWithPhoto, includeArchived, orderBy)
    @mcp.tool()
    async def get_item(id: str) -> str:
        """Get Item details by ID"""
        return await handle_get_item(client, id)
    @mcp.tool()
    async def get_item_link(query: str) -> str:
        """Get the direct link to an item by searching for it using asset ID, name, or description."""
        return await handle_get_item_link(client, query)
    @mcp.tool()
    async def create_item(
        name: str, locationId: str, description: str | None = None, quantity: int = 1, parentId: str | None = None,
        labelIds: list[str] | None = None, serialNumber: str | None = None, modelNumber: str | None = None,
        manufacturer: str | None = None, purchasePrice: float | None = None, notes: str | None = None, ctx: Context = None
    ) -> str:
        """Create a new item. Handles complex fields via a two-step create-and-update process. locationId is required."""
        return await handle_create_item(client, name, locationId, description, quantity, parentId, labelIds, serialNumber, modelNumber, manufacturer, purchasePrice, notes, ctx)
    @mcp.tool()
    async def update_item(
        id: str, name: str | None = None, description: str | None = None, quantity: int | None = None,
        locationId: str | None = None, parentId: str | None = None, labelIds: list[str] | None = None,
        serialNumber: str | None = None, modelNumber: str | None = None, manufacturer: str | None = None,
        purchasePrice: float | None = None, notes: str | None = None, fields: list[dict] | None = None, ctx: Context = None
    ) -> str:
        """Update an existing item (replaces existing with merged data)"""
        return await handle_update_item(client, id, name, description, quantity, locationId, parentId, labelIds, serialNumber, modelNumber, manufacturer, purchasePrice, notes, fields, ctx)
    @mcp.tool()
    async def patch_item(id: str, locationId: str | None = None, quantity: int | None = None, labelIds: list[str] | None = None) -> str:
        """Update item with PATCH (partial update). Only supports moving, quantity change, and labels."""
        return await handle_patch_item(client, id, locationId, quantity, labelIds)
    @mcp.tool()
    async def delete_item(id: str) -> str:
        """Delete an item"""
        return await handle_delete_item(client, id)
    @mcp.tool()
    async def get_item_by_asset_id(id: str) -> str:
        """Get Item by Asset ID (e.g. 1234)"""
        return await handle_get_item_by_asset_id(client, id)
    @mcp.tool()
    async def export_items() -> str:
        """Export items to CSV"""
        return await handle_export_items(client)
    @mcp.tool()
    async def get_item_fields() -> str:
        """Get all custom field names"""
        return await handle_get_item_fields(client)
    @mcp.tool()
    async def get_item_field_values(field: str) -> str:
        """Get all custom field values for a specific field name"""
        return await handle_get_item_field_values(client, field)
    @mcp.tool()
    async def duplicate_item(id: str, copyAttachments: bool = False, copyCustomFields: bool = False, copyMaintenance: bool = False, copyPrefix: str = "Copy of ") -> str:
        """Duplicate an item"""
        return await handle_duplicate_item(client, id, copyAttachments, copyCustomFields, copyMaintenance, copyPrefix)
    @mcp.tool()
    async def get_item_path(id: str) -> str:
        """Get full path of an item"""
        return await handle_get_item_path(client, id)
    @mcp.tool()
    async def get_item_attachment_token(id: str, attachment_id: str) -> str:
        """Get the download token for an item attachment"""
        return await handle_get_item_attachment_token(client, id, attachment_id)
    @mcp.tool()
    async def delete_item_attachment(id: str, attachment_id: str) -> str:
        """Delete item attachment"""
        return await handle_delete_item_attachment(client, id, attachment_id)
    @mcp.tool()
    async def update_item_attachment(id: str, attachment_id: str, primary: bool | None = None, title: str | None = None, type: str | None = None) -> str:
        """Update item attachment details."""
        return await handle_update_item_attachment(client, id, attachment_id, primary, title, type)
    @mcp.tool()
    async def get_item_maintenance(id: str, status: str = "both") -> str:
        """Get maintenance log"""
        return await handle_get_item_maintenance(client, id, status)
    @mcp.tool()
    async def create_item_maintenance(id: str, name: str, description: str | None = None, scheduledDate: str | None = None, completedDate: str | None = None, cost: float = 0) -> str:
        """Create maintenance entry"""
        return await handle_create_item_maintenance(client, id, name, description, scheduledDate, completedDate, cost)
    @mcp.tool()
    async def upload_item_attachment(item_id: str, file_path: str, primary: bool = False, attachment_type: str = "photo") -> str:
        """Upload an attachment to an item."""
        return await handle_upload_item_attachment(client, item_id, file_path, primary, attachment_type)
    @mcp.tool()
    async def import_items(file_path: str) -> str:
        """Import items from a CSV file."""
        return await handle_import_items(client, file_path)
    @mcp.tool()
    async def get_item_image(id: str) -> Image:
        """Retrieve the primary image for an item."""
        return await handle_get_item_image(client, id)
    # Tool Transformation Example: Specialized archived items list
    mcp.add_tool(Tool.from_tool(
        list_items, name="list_archived_items",
        description="Query only archived items in the inventory.",
        transform_args={"includeArchived": ArgTransform(hide=True, default=True)}
    ))