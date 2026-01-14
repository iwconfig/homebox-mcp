import json

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from homebox_mcp.client import HomeboxClient


def register_location_resources(mcp: FastMCP, client: HomeboxClient):
    """Register location-related resources."""

    @mcp.resource("homebox://locations", mime_type="application/json")
    async def list_locations() -> str:
        """
        List all locations in the inventory.
        URI: homebox://locations
        """
        locations = await client.list_locations()
        return json.dumps(locations, indent=2)

    @mcp.resource("homebox://locations/tree", mime_type="application/json")
    async def get_locations_tree() -> str:
        """
        Get the full location hierarchy as a tree.
        URI: homebox://locations/tree
        """
        tree = await client.get_locations_tree()
        return json.dumps(tree, indent=2)

    @mcp.resource("homebox://locations/{location_id}", mime_type="application/json")
    async def get_location(location_id: str) -> str:
        """
        Get details for a specific location by its UUID.
        URI: homebox://locations/{uuid}
        """
        location = await client.get_location(location_id)
        if not location:
            return json.dumps({"error": "Location not found", "id": location_id})
        return json.dumps(location, indent=2)

    @mcp.resource("homebox://locations/{location_id}/label", mime_type="image/png")
    async def get_location_label(location_id: str) -> Image:
        """
        Get the label QR code for a specific location.
        URI: homebox://locations/{uuid}/label
        """
        data = await client.get_label_image("location", location_id)
        return Image(data=data, format="png")
