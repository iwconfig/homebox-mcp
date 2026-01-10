from fastmcp import FastMCP

from homebox_mcp.client import HomeboxClient

from .items import register_item_resources
from .locations import register_location_resources


def register_all_resources(mcp: FastMCP, client: HomeboxClient):
    """Register all resources with the FastMCP server."""
    register_item_resources(mcp, client)
    register_location_resources(mcp, client)
