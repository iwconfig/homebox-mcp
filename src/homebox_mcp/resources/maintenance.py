import json

from fastmcp import FastMCP

from homebox_mcp.client import HomeboxClient


def register_maintenance_resources(mcp: FastMCP, client: HomeboxClient):
    """Register maintenance-related resources."""

    @mcp.resource("homebox://maintenance", mime_type="application/json")
    async def list_maintenance() -> str:
        """
        List all maintenance entries across the inventory.
        URI: homebox://maintenance
        """
        maintenance = await client.query_all_maintenance()
        return json.dumps(maintenance, indent=2)

    @mcp.resource("homebox://items/{item_id}/maintenance", mime_type="application/json")
    async def get_item_maintenance(item_id: str) -> str:
        """
        Get maintenance history for a specific item.
        URI: homebox://items/{item_id}/maintenance
        """
        maintenance = await client.get_item_maintenance(item_id)
        if maintenance is None:
            # get_item_maintenance returns [] if empty, None might mean error
            # or item not found depending on client impl
            # Checking client.py: query_all_maintenance returns list.
            # get_item_maintenance returns list.
            # If item doesn't exist, it might return empty list or error.
            # Let's assume empty list is fine, but if we want to be strict
            # we could check item existence.
            return json.dumps({"error": "Could not retrieve maintenance", "item_id": item_id})
        return json.dumps(maintenance, indent=2)
