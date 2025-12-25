import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_actions_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def create_missing_thumbnails() -> str:
        """Creates thumbnails for items that are missing them"""
        data = await client.request("POST", "actions/create-missing-thumbnails")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def ensure_asset_ids() -> str:
        """Ensures all items in the database have an asset ID"""
        data = await client.request("POST", "actions/ensure-asset-ids")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def ensure_import_refs() -> str:
        """Ensures all items in the database have an import ref"""
        data = await client.request("POST", "actions/ensure-import-refs")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def set_primary_photos() -> str:
        """Sets the first photo of each item as the primary photo"""
        data = await client.request("POST", "actions/set-primary-photos")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def zero_item_time_fields() -> str:
        """Resets all item date fields to the beginning of the day"""
        data = await client.request("POST", "actions/zero-item-time-fields")
        return json.dumps(data, indent=2)
