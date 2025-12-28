import json
import os
import mimetypes
import httpx
import base64
import re
import io
from ..client import HomeboxClient
from ..guardrails import protect_resource
from mcp.server.fastmcp import FastMCP

def register_items_tools(mcp: FastMCP, client: HomeboxClient):
    
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

    @mcp.tool()
    async def get_item(id: str) -> str:
        """Get Item details by ID"""
        data = await client.request("GET", f"items/{id}")
        link = client.get_web_url("item", data["id"])
        text = f"Item: {data.get('name')}\nLink: {link}\n\n"
        text += json.dumps(data, indent=2)
        return text

    @mcp.tool()
    async def get_item_link(query: str) -> str:
        """Get the direct link to an item by searching for it using asset ID, name, or description."""
        # Auto-prefix with # if it looks like an asset ID
        search_query = query
        if query.isdigit() or (("-" in query) and query.replace("-", "").isdigit()):
            if not query.startswith("#"):
                search_query = f"#{query}"
        
        data = await client.request("GET", "items", params={"q": search_query, "pageSize": 5})
        items = data.get("items", [])
        
        if not items and search_query != query:
            # Fallback to original query if # prefix failed
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

    @mcp.tool()
    @protect_resource(resource_type="items", action="create")
    async def create_item(
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
        """Create a new item. Handles complex fields via a two-step create-and-update process. locationId is required."""
        # Step 1: Create with minimal supported fields to avoid 500 errors
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
        
        # Step 2: Enrich with fields not supported by ItemCreate but supported by ItemUpdate
        # We fetch the full object first to ensure we have all defaults
        existing = await client.request("GET", f"items/{item_id}")
        update_payload = existing.copy()
        
        # Map IDs for PUT consistency
        if "location" in existing and existing["location"]:
            update_payload["locationId"] = existing["location"]["id"]
        if "parent" in existing and existing["parent"]:
            update_payload["parentId"] = existing["parent"]["id"]
        if "labels" in existing and existing["labels"]:
            update_payload["labelIds"] = [l["id"] for l in existing["labels"]]
        
        # Apply enriched fields
        if notes is not None: update_payload["notes"] = notes
        if serialNumber is not None: update_payload["serialNumber"] = serialNumber
        if modelNumber is not None: update_payload["modelNumber"] = modelNumber
        if manufacturer is not None: update_payload["manufacturer"] = manufacturer
        if purchasePrice is not None: update_payload["purchasePrice"] = float(purchasePrice)
        
        # Defaults for strict PUT
        for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
            if key not in update_payload: update_payload[key] = ""
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if key not in update_payload: update_payload[key] = "0001-01-01T00:00:00Z"

        final_item = await client.request("PUT", f"items/{item_id}", json=update_payload)
        return f"Created and Enriched Item: {json.dumps(final_item, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="items", action="update")
    async def update_item(
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
        """Update an existing item (replaces existing with merged data)"""
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
        if purchasePrice is not None: update_payload["purchasePrice"] = float(purchasePrice)
        if fields is not None: update_payload["fields"] = fields

        for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
            if key not in update_payload: update_payload[key] = existing.get(key, "")
        for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
            if key not in update_payload: update_payload[key] = existing.get(key, "0001-01-01T00:00:00Z")

        data = await client.request("PUT", f"items/{id}", json=update_payload)
        return f"Updated Item: {json.dumps(data, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="items", action="update")
    async def patch_item(
        id: str, 
        locationId: str = None, 
        quantity: int = None, 
        labelIds: list[str] = None
    ) -> str:
        """Update item with PATCH (partial update). Only supports moving, quantity change, and labels."""
        payload = {}
        if locationId: payload["locationId"] = locationId
        if quantity is not None: payload["quantity"] = quantity
        if labelIds is not None: payload["labelIds"] = labelIds
        
        data = await client.request("PATCH", f"items/{id}", json=payload)
        return f"Patched Item: {json.dumps(data, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="items", action="delete")
    async def delete_item(id: str) -> str:
        """Delete an item"""
        await client.request("DELETE", f"items/{id}")
        return f"Deleted item {id}"

    @mcp.tool()
    async def get_item_by_asset_id(id: str) -> str:
        """Get Item by Asset ID (e.g. 1234)"""
        data = await client.request("GET", f"assets/{id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def export_items() -> str:
        """Export items to CSV"""
        data = await client.request("GET", "items/export")
        return data

    @mcp.tool()
    async def get_item_fields() -> str:
        """Get all custom field names"""
        data = await client.request("GET", "items/fields")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_item_field_values() -> str:
        """Get all custom field values"""
        data = await client.request("GET", "items/fields/values")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def duplicate_item(
        id: str, 
        copyAttachments: bool = False,
        copyCustomFields: bool = False,
        copyMaintenance: bool = False,
        copyPrefix: str = "Copy of "
    ) -> str:
        """Duplicate an item"""
        payload = {
            "copyAttachments": copyAttachments,
            "copyCustomFields": copyCustomFields,
            "copyMaintenance": copyMaintenance,
            "copyPrefix": copyPrefix
        }
        data = await client.request("POST", f"items/{id}/duplicate", json=payload)
        return f"Duplicated Item: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_item_path(id: str) -> str:
        """Get full path of an item"""
        data = await client.request("GET", f"items/{id}/path")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def delete_item_attachment(id: str, attachment_id: str) -> str:
        """Delete item attachment"""
        await client.request("DELETE", f"items/{id}/attachments/{attachment_id}")
        return "Deleted attachment"

    @mcp.tool()
    async def update_item_attachment(
        id: str, 
        attachment_id: str, 
        primary: bool = None, 
        title: str = None, 
        type: str = None
    ) -> str:
        """
        Update item attachment details.
        Type must be one of: 'photo', 'manual', 'warranty', 'receipt', 'attachment'.
        """
        payload = {}
        if primary is not None: payload["primary"] = primary
        if title is not None: payload["title"] = title
        if type is not None: payload["type"] = type
        
        data = await client.request("PUT", f"items/{id}/attachments/{attachment_id}", json=payload)
        return f"Updated Attachment: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_item_maintenance(id: str, status: str = "both") -> str:
        """Get maintenance log"""
        data = await client.request("GET", f"items/{id}/maintenance", params={"status": status})
        return json.dumps(data, indent=2)

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
        payload = {"name": name, "cost": cost}
        if description: payload["description"] = description
        if scheduledDate: payload["scheduledDate"] = scheduledDate
        if completedDate: payload["completedDate"] = completedDate
        
        data = await client.request("POST", f"items/{id}/maintenance", json=payload)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def upload_item_attachment(
        item_id: str,
        file_path: str,
        primary: bool = False,
        attachment_type: str = "photo"
    ) -> str:
        """
        Upload an attachment to an item.
        
        Args:
            item_id: The ID of the item to attach to.
            file_path: Source of the file. Can be:
                      1. Absolute local path (e.g. /tmp/img.jpg)
                      2. HTTP/HTTPS URL (e.g. https://example.com/img.jpg)
                      3. Base64 Data URI (e.g. data:image/png;base64,iVBOR...)
            primary: Whether this is the primary image/attachment.
            attachment_type: Type of attachment (e.g. 'photo', 'document').
        """
        file_name = "upload"
        mime_type = 'application/octet-stream'
        file_content = b""

        # Case 1: Base64 Data URI
        if file_path.startswith("data:"):
            try:
                header, encoded = file_path.split(",", 1)
                mime_type = header.split(";")[0].split(":")[1]
                file_content = base64.b64decode(encoded)
                # Try to guess extension from mime-type
                ext = mimetypes.guess_extension(mime_type) or ".bin"
                file_name = f"upload{ext}"
            except Exception as e:
                return f"Error: Failed to decode base64 data: {str(e)}"

        # Case 2: HTTP/HTTPS URL
        elif file_path.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.get(file_path, follow_redirects=True)
                    resp.raise_for_status()
                    file_content = resp.content
                    mime_type = resp.headers.get("content-type", "").split(";")[0] or mime_type
                    # Try to get filename from URL
                    file_name = os.path.basename(file_path.split("?")[0]) or "upload"
                    if "." not in file_name:
                         ext = mimetypes.guess_extension(mime_type) or ""
                         file_name += ext
            except Exception as e:
                return f"Error: Failed to download from URL: {str(e)}"

        # Case 3: Local File Path
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
            
        files = {
            'file': (file_name, file_content, mime_type)
        }
        
        data = {
            'name': file_name,
            'type': attachment_type,
            'primary': 'true' if primary else 'false'
        }
        
        try:
            result = await client.request(
                "POST", 
                f"items/{item_id}/attachments", 
                files=files, 
                data=data
            )
            return f"Attachment uploaded successfully: {json.dumps(result, indent=2)}"
        except Exception as e:
            return f"Failed to upload attachment: {str(e)}"

    @mcp.tool()
    async def import_items(file_path: str) -> str:
        """
        Import items from a CSV file.
        
        Args:
            file_path: Absolute path to the local CSV file.
        """
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        file_name = os.path.basename(file_path)
        mime_type = 'text/csv'
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
            
        files = {
            'csv': (file_name, file_content, mime_type)
        }
        
        try:
            # This endpoint returns 204 No Content on success
            await client.request(
                "POST", 
                "items/import", 
                files=files
            )
            return "Items imported successfully."
        except Exception as e:
            return f"Failed to import items: {str(e)}"
