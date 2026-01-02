from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_all_resources(mcp: FastMCP, client: HomeboxClient):
    from . import inbox, images
    
    inbox.register_inbox_resource(mcp, client)
    images.register_image_resource(mcp, client)
