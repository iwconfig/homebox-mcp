import json

from fastmcp import FastMCP

from homebox_mcp.client import HomeboxClient


def register_item_resources(mcp: FastMCP, client: HomeboxClient):
    """Register item-related resources."""

    @mcp.resource("homebox://items")
    async def list_items() -> str:
        """
        List all items in the inventory.
        URI: homebox://items
        """
        items = await client.list_items()
        return json.dumps(items, indent=2)

    @mcp.resource("homebox://items/{item_id}")
    async def get_item(item_id: str) -> str:
        """
        Get details for a specific item by its UUID.
        URI: homebox://items/{uuid}
        Example: homebox://items/550e8400-e29b-41d4-a716-446655440000
        """
        item = await client.get_item(item_id)
        if not item:
            return json.dumps({"error": "Item not found", "id": item_id})
        return json.dumps(item, indent=2)

    @mcp.resource("homebox://assets/{asset_id}")
    async def get_asset(asset_id: str) -> str:
        """
        Get details for a specific item by its Asset ID.
        Supports hyphenated (000-001), padded (000001), or raw (1) formats.
        URI: homebox://assets/{asset_id}
        Example: homebox://assets/000-001
        """
        # The backend handles the normalization (stripping hyphens and parsing as int)
        # but the client method might need to know it's getting a pagination result.
        result = await client.get_item_by_asset_id(asset_id)
        
        # If result is a list (pagination result), try to get the first item
        if isinstance(result, dict) and "items" in result:
            items = result["items"]
            if items:
                return json.dumps(items[0], indent=2)
            return json.dumps({"error": "No item found for asset ID", "asset_id": asset_id})
            
        return json.dumps(result, indent=2)
