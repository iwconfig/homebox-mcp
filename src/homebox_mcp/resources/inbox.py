import json
import logging
import os
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

# Cache for Inbox Location ID to avoid redundant lookups
_INBOX_ID_CACHE = None

async def get_inbox_items(client: HomeboxClient) -> str:
    """Helper to find items in the Inbox location."""
    global _INBOX_ID_CACHE
    
    inbox_name = os.getenv("HOMEBOX_INBOX_LOCATION", "Inbox")
    inbox_id = os.getenv("HOMEBOX_INBOX_LOCATION_ID") or _INBOX_ID_CACHE
    
    try:
        if not inbox_id:
            logger.info(f"Looking up location ID for '{inbox_name}'")
            locations_data = await client.request("GET", "locations")
            if isinstance(locations_data, dict) and "items" in locations_data:
                locations = locations_data["items"]
            else:
                locations = locations_data
                
            # Simple search if it's a flat list
            queue = list(locations)
            while queue:
                loc = queue.pop(0)
                if loc.get("name", "").lower() == inbox_name.lower():
                    inbox_id = loc["id"]
                    _INBOX_ID_CACHE = inbox_id
                    break
                if "children" in loc:
                    queue.extend(loc["children"])
                    
        if not inbox_id:
            return f"Error: Location '{inbox_name}' not found. Please set HOMEBOX_INBOX_LOCATION or HOMEBOX_INBOX_LOCATION_ID."

        # 2. List items in that location
        data = await client.request("GET", "items", params={"locations": [inbox_id], "pageSize": 50})
        items_summary = data.get("items", [])
        
        if not items_summary:
            return "[]"
            
        # Fetch details for each item to get attachments
        import asyncio
        tasks = [client.request("GET", f"items/{item['id']}") for item in items_summary]
        items_details = await asyncio.gather(*tasks)
        
        # 3. Format as simplified JSON for the agent
        summary = []
        for item in items_details:
            attachments = []
            for att in item.get("attachments", []):
                resource_uri = f"homebox://items/{item['id']}/attachments/{att['id']}/image"
                attachments.append({
                    "id": att["id"],
                    "name": att.get("name") or att.get("title"),
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
