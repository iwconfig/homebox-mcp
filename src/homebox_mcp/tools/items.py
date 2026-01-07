import json
import os
import mimetypes
import httpx
import base64
import re
import io
from typing import Any, Literal, Optional
from datetime import datetime, timezone
from ..client import HomeboxClient
from ..guardrails import protect_resource
from ..resources.inbox import get_inbox_items
from ..resources.images import fetch_and_anonymize_image
from mcp.server.fastmcp import FastMCP

# --- Utilities ---

def get_id(text: str) -> str:
    """Helper to extract UUID from tool responses, prioritizing JSON parsing."""
    if not text:
        return None
    
    # 1. Try to extract and parse JSON block if present
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            data = json.loads(text[start:end+1])
            if isinstance(data, dict) and 'id' in data:
                return data['id']
            if isinstance(data, dict) and 'item' in data and isinstance(data['item'], dict):
                return data['item'].get('id')
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Regex fallback for plain text or malformed snippets
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r'ID: ([a-f0-9\-]+)', text)
    if m:
        return m.group(1)
    return None

# --- Tool Handlers ---

async def handle_get_inbox_queue(client: HomeboxClient) -> str:
    """Returns a unified list of items in the Inbox (from Homebox API and local directory) that require processing."""
    return await get_inbox_items(client)

async def handle_get_inbox_image(client: HomeboxClient, id: str, attachment_id: str = None) -> Any:
    """Returns the binary image data for an inbox item (local or server)."""
    from mcp.types import ImageContent
    import base64
    
    # attachment_id is only needed for source='homebox'
    data = await fetch_and_anonymize_image(client, id, attachment_id)
    b64 = base64.b64encode(data).decode("utf-8")
    return [ImageContent(type="image", data=b64, mimeType="image/jpeg")]

async def handle_finalize_processed_item(
    client: HomeboxClient,
    id: str,
    name: str,
    locationId: str,
    description: Optional[str] = None,
    labelIds: Optional[list[str]] = None,
    notes: Optional[str] = None,
    source: Literal["homebox", "local"] = "homebox",
    rotation: Optional[int] = None,
    extracted_objects: Optional[list[dict]] = None,
    manufacturer: Optional[str] = None,
    modelNumber: Optional[str] = None,
    serialNumber: Optional[str] = None
) -> str:
    """
    Finalizes an item by updating metadata and moving it to a new location.
    If source is 'local', it handles the initial upload to Homebox.
    Supports optional rotation and extracting multiple objects.
    """
    from .images import handle_rotate_image, handle_split_item_from_image
    
    result = {
        "status": "success",
        "item_id": id,
        "actions": []
    }

    try:
        # 1. Handle Object Extraction (Exclusive mode)
        if extracted_objects:
            # For extraction, we need an attachment_id if source is homebox
            att_id = None
            if source == "homebox":
                item = await client.request("GET", f"items/{id}")
                atts = item.get("attachments", [])
                if not atts:
                    return json.dumps({"status": "error", "error": "Cannot extract objects from item without attachments."})
                att_id = next((a["id"] for a in atts if a.get("primary")), atts[0]["id"])
            
            extract_res_json = await handle_split_item_from_image(client, id, extracted_objects, source, att_id)
            extract_res = json.loads(extract_res_json)
            
            if extract_res["status"] == "error":
                return extract_res_json
                
            result["actions"].append("extracted_into_objects")
            result["extraction_details"] = extract_res
            return json.dumps(result, indent=2)

        # 2. Handle Rotation
        if rotation and source == "homebox":
            item = await client.request("GET", f"items/{id}")
            atts = item.get("attachments", [])
            if atts:
                att_id = next((a["id"] for a in atts if a.get("primary")), atts[0]["id"])
                rot_res = await handle_rotate_image(client, id, att_id, rotation)
                if "Error" not in rot_res:
                    result["actions"].append(f"rotated_{rotation}_deg")

        # 3. Standard Processing (Metadata + Move)
        if source == "local":
            create_res = await handle_create_item(
                client, name=name, locationId=locationId,
                manufacturer=manufacturer, modelNumber=modelNumber, serialNumber=serialNumber
            )
            target_item_id = get_id(create_res)
            
            if not target_item_id:
                return json.dumps({
                    "status": "error",
                    "error": "Failed to create item for local file", 
                    "details": create_res
                })
            
            result["item_id"] = target_item_id
            result["actions"].append("created_item")
                
            full_path = None
            if os.path.isabs(id):
                full_path = id
            else:
                inbox_dir = os.getenv("HOMEBOX_INBOX_DIRECTORY")
                if inbox_dir:
                    full_path = os.path.join(inbox_dir, id)
            
            if not full_path or not os.path.exists(full_path):
                 return json.dumps({"status": "error", "error": f"Local file not found: {id}"})

            await handle_upload_item_attachment(client, target_item_id, full_path, primary=True)
            result["actions"].append("uploaded_file")
            
            await handle_update_item(
                client, target_item_id, name=name, locationId=locationId, 
                description=description, labelIds=labelIds, notes=notes,
                manufacturer=manufacturer, modelNumber=modelNumber, serialNumber=serialNumber
            )
            result["actions"].append("updated_metadata")
            
            try:
                os.remove(full_path)
                result["actions"].append("deleted_local_file")
            except Exception as e:
                result["warnings"] = [f"Failed to delete local file: {str(e)}"]
                
        else:
            await handle_update_item(
                client, id, name=name, locationId=locationId, 
                description=description, labelIds=labelIds, notes=notes,
                manufacturer=manufacturer, modelNumber=modelNumber, serialNumber=serialNumber
            )
            result["actions"].append("updated_and_moved")
            
        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)

async def handle_list_items(
    client: HomeboxClient,
    q: str = None,
    page: int = 1,
    pageSize: int = 50,
    labels: list[str] = None,
    locations: list[str] = None,
    parentIds: list[str] = None
) -> str:
    params = {}
    if q: params["q"] = q
    if page: params["page"] = page
    if pageSize: params["pageSize"] = pageSize
    if labels: params["labels"] = labels
    if locations: params["locations"] = locations
    if parentIds: params["parentIds"] = parentIds
    
    data = await client.request("GET", "items", params=params)
    items = data.get("items", [])
    output = f"Found {data.get('total', len(items))} items (Page {data.get('page', 1)}/{data.get('totalPages', '?')})\n\n"
    
    for item in items:
        link = client.get_web_url("item", item["id"])
        output += f"- [{item.get('name')}]({link}) (ID: {item.get('id')})\n"
        if item.get("location"):
             output += f"  Location: {item['location'].get('name')}\n"
        if item.get("quantity"):
             output += f"  Qty: {item['quantity']}\n"
             
    return output

async def handle_get_item(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"items/{id}")
    link = client.get_web_url("item", data["id"])
    text = f"Item: {data.get('name')}\nLink: {link}\n\n"
    text += json.dumps(data, indent=2)
    return text

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
    description: str = None,
    quantity: int = 1,
    parentId: str = None,
    labelIds: list[str] = None,
    serialNumber: str = None,
    modelNumber: str = None,
    manufacturer: str = None,
    purchasePrice: float = None,
    notes: str = None
) -> str:
    create_payload = {
        "name": name,
        "quantity": int(quantity) if quantity is not None else 1,
        "description": description or "",
        "labelIds": labelIds or [],
        "locationId": locationId
    }
    if parentId: create_payload["parentId"] = parentId
    
    created_item = await client.request("POST", "items", json=create_payload)
    item_id = created_item["id"]
    
    try:
        # Use the created item as the base for update, avoiding redundant GET
        update_payload = created_item.copy()
        
        # Ensure ID-based fields are correctly mapped if the server returned full objects
        if "location" in created_item and created_item["location"]:
            update_payload["locationId"] = created_item["location"]["id"]
        elif locationId:
            update_payload["locationId"] = locationId
            
        if "parent" in created_item and created_item["parent"]:
            update_payload["parentId"] = created_item["parent"]["id"]
        elif parentId:
            update_payload["parentId"] = parentId
            
        if "labels" in created_item and created_item["labels"]:
            update_payload["labelIds"] = [l["id"] for l in created_item["labels"]]
        elif labelIds:
             update_payload["labelIds"] = labelIds
        
        if notes is not None: update_payload["notes"] = notes
        if serialNumber is not None: update_payload["serialNumber"] = serialNumber
        if modelNumber is not None: update_payload["modelNumber"] = modelNumber
        if manufacturer is not None: update_payload["manufacturer"] = manufacturer
        if purchasePrice is not None: update_payload["purchasePrice"] = str(purchasePrice)
        
        for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
            if key not in update_payload: update_payload[key] = ""
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if key not in update_payload: update_payload[key] = "0001-01-01T00:00:00Z"

        final_item = await client.request("PUT", f"items/{item_id}", json=update_payload)
        return f"Created and Enriched Item: {json.dumps(final_item, indent=2)}"
        
    except Exception as e:
        # Rollback: Delete the partially created item
        try:
            await client.request("DELETE", f"items/{item_id}")
        except Exception:
            # Swallow delete error to raise the original enrichment error
            pass
        raise e

@protect_resource(resource_type="items", action="update")
async def handle_update_item(
    client: HomeboxClient,
    id: str,
    name: str = None,
    description: str = None,
    quantity: int = None,
    locationId: str = None,
    parentId: str = None,
    labelIds: list[str] = None,
    serialNumber: str = None,
    modelNumber: str = None,
    manufacturer: str = None,
    purchasePrice: float = None,
    notes: str = None,
    fields: list[dict] = None
) -> str:
    existing = await client.request("GET", f"items/{id}")
    update_payload = existing.copy()
    
    if "location" in existing and existing["location"]:
        update_payload["locationId"] = existing["location"]["id"]
    if "parent" in existing and existing["parent"]:
        update_payload["parentId"] = existing["parent"]["id"]
    if "labels" in existing and existing["labels"]:
        update_payload["labelIds"] = [l["id"] for l in existing["labels"]]

    if name is not None: update_payload["name"] = name
    if description is not None: update_payload["description"] = description
    if notes is not None: update_payload["notes"] = notes
    if quantity is not None: update_payload["quantity"] = int(quantity)
    if locationId is not None: update_payload["locationId"] = locationId
    if parentId is not None: update_payload["parentId"] = parentId
    if labelIds is not None: update_payload["labelIds"] = labelIds
    if serialNumber is not None: update_payload["serialNumber"] = serialNumber
    if modelNumber is not None: update_payload["modelNumber"] = modelNumber
    if manufacturer is not None: update_payload["manufacturer"] = manufacturer
    if purchasePrice is not None: update_payload["purchasePrice"] = str(purchasePrice)
    if fields is not None: update_payload["fields"] = fields

    for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
        if key not in update_payload: update_payload[key] = existing.get(key, "")
    for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
        if key not in update_payload: update_payload[key] = existing.get(key, "0001-01-01T00:00:00Z")

    data = await client.request("PUT", f"items/{id}", json=update_payload)
    return f"Updated Item: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="items", action="update")
async def handle_patch_item(
    client: HomeboxClient,
    id: str, 
    locationId: str = None, 
    quantity: int = None, 
    labelIds: list[str] = None
) -> str:
    payload = {}
    if locationId: payload["locationId"] = locationId
    if quantity is not None: payload["quantity"] = quantity
    if labelIds: payload["labelIds"] = labelIds
    
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

async def handle_duplicate_item(
    client: HomeboxClient,
    id: str, 
    copyAttachments: bool = False,
    copyCustomFields: bool = False,
    copyMaintenance: bool = False,
    copyPrefix: str = "Copy of "
) -> str:
    payload = {
        "copyAttachments": copyAttachments,
        "copyCustomFields": copyCustomFields,
        "copyMaintenance": copyMaintenance,
        "copyPrefix": copyPrefix
    }
    data = await client.request("POST", f"items/{id}/duplicate", json=payload)
    return f"Duplicated Item: {json.dumps(data, indent=2)}"

async def handle_get_item_path(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"items/{id}/path")
    return json.dumps(data, indent=2)

async def handle_get_item_attachment_token(client: HomeboxClient, id: str, attachment_id: str) -> str:
    data = await client.request("GET", f"items/{id}/attachments/{attachment_id}")
    if isinstance(data, bytes):
        import base64
        return json.dumps({
            "attachment_id": attachment_id,
            "data_base64": base64.b64encode(data).decode("utf-8"),
            "hint": "This is binary data encoded in base64."
        }, indent=2)
    return json.dumps(data, indent=2)

async def handle_delete_item_attachment(client: HomeboxClient, id: str, attachment_id: str) -> str:
    await client.request("DELETE", f"items/{id}/attachments/{attachment_id}")
    return "Deleted attachment"

async def handle_update_item_attachment(
    client: HomeboxClient,
    id: str, 
    attachment_id: str, 
    primary: bool = None, 
    title: str = None, 
    type: str = None
) -> str:
    item = await client.request("GET", f"items/{id}")
    existing = next((a for a in item.get("attachments", []) if a["id"] == attachment_id), None)
    if not existing:
        return f"Error: Attachment {attachment_id} not found on item {id}"

    payload = {
        "primary": primary if primary is not None else existing.get("primary", False),
        "title": title if title is not None else existing.get("title", ""),
        "type": type if type is not None else existing.get("type", "attachment")
    }
    
    data = await client.request("PUT", f"items/{id}/attachments/{attachment_id}", json=payload)
    return f"Updated Attachment: {json.dumps(data, indent=2)}"

async def handle_get_item_maintenance(client: HomeboxClient, id: str, status: str = "both") -> str:
    data = await client.request("GET", f"items/{id}/maintenance", params={"status": status})
    return json.dumps(data, indent=2)

async def handle_create_item_maintenance(
    client: HomeboxClient,
    id: str, 
    name: str, 
    description: str = None, 
    scheduledDate: str = None, 
    completedDate: str = None,
    cost: float = 0
) -> str:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "name": name, 
        "cost": str(cost),
        "description": description or "",
        "scheduledDate": scheduledDate or now_iso,
        "completedDate": completedDate or "0001-01-01T00:00:00Z"
    }
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
    file_name = "upload"
    mime_type = 'application/octet-stream'
    file_content = b""

    if file_path.startswith("data:"):
        try:
            header, encoded = file_path.split(",", 1)
            mime_type = header.split(";")[0].split(":")[1]
            file_content = base64.b64decode(encoded)
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            file_name = f"upload{ext}"
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
                     ext = mimetypes.guess_extension(mime_type) or ""
                     file_name += ext
        except Exception as e:
            return f"Error: Failed to download from URL: {str(e)}"
    else:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or mime_type
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            return f"Error: Failed to read local file: {str(e)}"
        
    files = {'file': (file_name, file_content, mime_type)}
    data = {'name': file_name, 'type': attachment_type, 'primary': 'true' if primary else 'false'}
    try:
        result = await client.request("POST", f"items/{item_id}/attachments", files=files, data=data)
        return f"Attachment uploaded successfully: {json.dumps(result, indent=2)}"
    except Exception as e:
        return f"Failed to upload attachment: {str(e)}"

async def handle_import_items(client: HomeboxClient, file_path: str) -> str:
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    file_name = os.path.basename(file_path)
    mime_type = 'text/csv'
    with open(file_path, 'rb') as f:
        file_content = f.read()
    files = {'csv': (file_name, file_content, mime_type)}
    try:
        await client.request("POST", "items/import", files=files)
        return "Items imported successfully."
    except Exception as e:
        return f"Failed to import items: {str(e)}"


# --- Registration ---

def register_items_tools(mcp: FastMCP, client: HomeboxClient):
    
    @mcp.tool()
    async def get_inbox_queue() -> str:
        """Returns a unified list of items in the Inbox (from Homebox API and local directory) that require processing."""
        return await handle_get_inbox_queue(client)

    @mcp.tool()
    async def get_inbox_image(id: str, attachment_id: str = None) -> Any:
        """Retrieve the binary image data for an inbox item (local file or server attachment)."""
        return await handle_get_inbox_image(client, id, attachment_id)

    @mcp.tool()
    async def finalize_processed_item(
        id: str,
        name: str,
        locationId: str,
        description: Optional[str] = None,
        labelIds: Optional[list[str]] = None,
        notes: Optional[str] = None,
        source: Literal["homebox", "local"] = "homebox",
        rotation: Optional[int] = None,
        extracted_objects: Optional[list[dict]] = None,
        manufacturer: Optional[str] = None,
        modelNumber: Optional[str] = None,
        serialNumber: Optional[str] = None
    ) -> str:
        """
        Finalizes an item by updating metadata and moving it to a new location.
        If source is 'local', it handles the initial upload to Homebox.
        Supports optional rotation (any degree, e.g. 15, -90) and extracting multiple objects via crop boxes.
        If extracted_objects is used, the source item is deleted.
        Returns a JSON object with the result status and actions taken.
        """
        return await handle_finalize_processed_item(
            client, id, name, locationId, description, labelIds, notes, source, rotation, extracted_objects,
            manufacturer, modelNumber, serialNumber
        )

    @mcp.tool()
    async def list_items(
        q: str = None,
        page: int = 1,
        pageSize: int = 50,
        labels: list[str] = None,
        locations: list[str] = None,
        parentIds: list[str] = None
    ) -> str:
        """Query All Items. Supports filtering and pagination."""
        return await handle_list_items(client, q, page, pageSize, labels, locations, parentIds)

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
        name: str,
        locationId: str,
        description: Optional[str] = None,
        quantity: int = 1,
        parentId: Optional[str] = None,
        labelIds: Optional[list[str]] = None,
        serialNumber: Optional[str] = None,
        modelNumber: Optional[str] = None,
        manufacturer: Optional[str] = None,
        purchasePrice: Optional[float] = None,
        notes: Optional[str] = None
    ) -> str:
        """Create a new item. Handles complex fields via a two-step create-and-update process. locationId is required."""
        return await handle_create_item(client, name, locationId, description, quantity, parentId, labelIds, serialNumber, modelNumber, manufacturer, purchasePrice, notes)

    @mcp.tool()
    async def update_item(
        id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        quantity: Optional[int] = None,
        locationId: Optional[str] = None,
        parentId: Optional[str] = None,
        labelIds: Optional[list[str]] = None,
        serialNumber: Optional[str] = None,
        modelNumber: Optional[str] = None,
        manufacturer: Optional[str] = None,
        purchasePrice: Optional[float] = None,
        notes: Optional[str] = None,
        fields: Optional[list[dict]] = None
    ) -> str:
        """Update an existing item (replaces existing with merged data)"""
        return await handle_update_item(client, id, name, description, quantity, locationId, parentId, labelIds, serialNumber, modelNumber, manufacturer, purchasePrice, notes, fields)

    @mcp.tool()
    async def patch_item(
        id: str, 
        locationId: str = None, 
        quantity: int = None, 
        labelIds: list[str] = None
    ) -> str:
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
    async def duplicate_item(
        id: str, 
        copyAttachments: bool = False,
        copyCustomFields: bool = False,
        copyMaintenance: bool = False,
        copyPrefix: str = "Copy of "
    ) -> str:
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
    async def update_item_attachment(
        id: str, 
        attachment_id: str, 
        primary: bool = None, 
        title: str = None, 
        type: str = None
    ) -> str:
        """Update item attachment details."""
        return await handle_update_item_attachment(client, id, attachment_id, primary, title, type)

    @mcp.tool()
    async def get_item_maintenance(id: str, status: str = "both") -> str:
        """Get maintenance log"""
        return await handle_get_item_maintenance(client, id, status)

    @mcp.tool()
    async def create_item_maintenance(
        id: str, 
        name: str, 
        description: str = None, 
        scheduledDate: str = None, 
        completedDate: str = None,
        cost: float = 0
    ) -> str:
        """Create maintenance entry"""
        return await handle_create_item_maintenance(client, id, name, description, scheduledDate, completedDate, cost)

    @mcp.tool()
    async def upload_item_attachment(
        item_id: str,
        file_path: str,
        primary: bool = False,
        attachment_type: str = "photo"
    ) -> str:
        """Upload an attachment to an item."""
        return await handle_upload_item_attachment(client, item_id, file_path, primary, attachment_type)

    @mcp.tool()
    async def import_items(file_path: str) -> str:
        """Import items from a CSV file."""
        return await handle_import_items(client, file_path)
