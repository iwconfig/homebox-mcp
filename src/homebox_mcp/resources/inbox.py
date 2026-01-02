import json
import logging
import os
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def get_inbox_items(client: HomeboxClient) -> str:
    """Helper to find items in the Inbox location."""
    inbox_name = os.getenv("HOMEBOX_INBOX_LOCATION", "Inbox")
    
    # 1. Find the Location ID for "Inbox"
    # We might want to cache this, but for now let's just fetch.
    # Note: list_locations usually returns a tree or list. 
    # If list_locations supports filtering by name, great. If not, we iterate.
    # Based on client implementation, getting all locations and filtering is safer.
    
    try:
        # Assuming we can get all locations. Using a large pageSize if possible or walking the tree.
        # client.request("GET", "locations") usually returns a list or tree.
        locations_data = await client.request("GET", "locations")
        if isinstance(locations_data, dict) and "items" in locations_data:
            locations = locations_data["items"]
        else:
            locations = locations_data
            
        inbox_id = None
        
        # Simple BFS or linear search if it's a flat list
        queue = list(locations)
        while queue:
            loc = queue.pop(0)
            if loc.get("name", "").lower() == inbox_name.lower():
                inbox_id = loc["id"]
                break
            if "children" in loc:
                queue.extend(loc["children"])
                
        if not inbox_id:
            return f"Error: Location '{inbox_name}' not found."

        # 2. List items in that location
        # Using the list_items endpoint which supports location filtering
        data = await client.request("GET", "items", params={"locations": [inbox_id], "pageSize": 100})
        items = data.get("items", [])
        
        # 3. Format as simplified JSON for the agent
        summary = []
        for item in items:
            attachments = []
            for att in item.get("attachments", []):
                # Construct the MCP resource URI for the image
                # Format: homebox://items/{id}/attachments/{attachment_id}/image
                resource_uri = f"homebox://items/{item['id']}/attachments/{att['id']}/image"
                attachments.append({
                    "id": att["id"],
                    "name": att.get("name"),
                    "resource": resource_uri
                })
                
            summary.append({
                "id": item["id"],
                "name": item["name"],
                "attachments": attachments
            })
            
        return json.dumps(summary, indent=2)

    except Exception as e:
        logger.error(f"Failed to fetch inbox: {e}")
        return f"Error fetching inbox: {str(e)}"

def register_inbox_resource(mcp: FastMCP, client: HomeboxClient):
    @mcp.resource("homebox://inbox/queue")
    async def inbox_queue() -> str:
        """Returns a list of items in the Inbox that require processing."""
        return await get_inbox_items(client)
