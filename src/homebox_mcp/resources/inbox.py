import json
import logging
import os
import asyncio
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

# Cache for Inbox Location ID to avoid redundant lookups
_INBOX_ID_CACHE = None

async def get_inbox_items(client: HomeboxClient) -> str:
    """Helper to find items in the Inbox location AND local directory."""
    global _INBOX_ID_CACHE
    
    inbox_name = os.getenv("HOMEBOX_INBOX_LOCATION", "Inbox")
    inbox_id = os.getenv("HOMEBOX_INBOX_LOCATION_ID") or _INBOX_ID_CACHE
    inbox_dir = os.getenv("HOMEBOX_INBOX_DIRECTORY")
    
    combined_queue = []

    # 1. Fetch from Local Directory (if configured)
    if inbox_dir and os.path.exists(inbox_dir):
        try:
            for f in os.listdir(inbox_dir):
                full_path = os.path.join(inbox_dir, f)
                if os.path.isfile(full_path):
                    # We treat local files as "virtual" items
                    combined_queue.append({
                        "id": f,
                        "name": f,
                        "source": "local",
                        "attachments": [{
                            "id": f,
                            "name": f,
                            "resource": f"homebox://local/inbox/{f}"
                        }]
                    })
        except Exception as e:
            logger.error(f"Failed to scan local inbox: {e}")

    # 2. Fetch from Homebox API
    try:
        if not inbox_id:
            locations_data = await client.request("GET", "locations")
            if isinstance(locations_data, dict):
                locations = locations_data.get("items", [])
            else:
                locations = locations_data if isinstance(locations_data, list) else []
            
            queue = list(locations)
            while queue:
                loc = queue.pop(0)
                if loc.get("name", "").lower() == inbox_name.lower():
                    inbox_id = loc["id"]
                    _INBOX_ID_CACHE = inbox_id
                    break
                if "children" in loc:
                    queue.extend(loc["children"])
                    
        if inbox_id:
            data = await client.request("GET", "items", params={"locations": [inbox_id], "pageSize": 50})
            items_summary = data.get("items", [])
            
            if items_summary:
                tasks = [client.request("GET", f"items/{item['id']}") for item in items_summary]
                items_details = await asyncio.gather(*tasks)
                
                for item in items_details:
                    attachments = []
                    for att in item.get("attachments", []):
                        resource_uri = f"homebox://items/{item['id']}/attachments/{att['id']}/image"
                        attachments.append({
                            "id": att["id"],
                            "name": att.get("name") or att.get("title"),
                            "resource": resource_uri
                        })
                        
                    combined_queue.append({
                        "id": item["id"],
                        "name": item["name"],
                        "source": "homebox",
                        "attachments": attachments
                    })

    except Exception as e:
        logger.error(f"Failed to fetch API inbox: {e}")
        # If we have local items, we still return them even if API fails
        if not combined_queue:
            return f"Error fetching inbox: {str(e)}"

    return json.dumps(combined_queue, indent=2)

def register_inbox_resource(mcp: FastMCP, client: HomeboxClient):
    @mcp.resource("homebox://inbox/queue")
    async def inbox_queue() -> str:
        """Returns a list of items in the Inbox that require processing."""
        return await get_inbox_items(client)
