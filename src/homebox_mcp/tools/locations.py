import json
from ..client import HomeboxClient
from ..guardrails import protect_resource
from fastmcp import FastMCP

# --- Tool Handlers ---

async def handle_list_locations(client: HomeboxClient, filterChildren: bool = False) -> str:
    """Get All Locations."""
    params = {"filterChildren": str(filterChildren).lower()}
    data = await client.request("GET", "locations", params=params)
    
    output = f"Found {len(data)} locations:\n\n"
    for loc in data:
        link = client.get_web_url("location", loc["id"])
        output += f"- [{loc.get('name')}]({link}) (ID: {loc.get('id')}) - Items: {loc.get('itemCount', 0)}\n"
        
    return output

@protect_resource(resource_type="locations", action="create")
async def handle_create_location(client: HomeboxClient, name: str, description: str | None = None, parentId: str | None = None) -> str:
    """Create a new location."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if parentId:
        payload["parentId"] = parentId
        
    data = await client.request("POST", "locations", json=payload)
    return f"Created Location: {json.dumps(data, indent=2)}"

async def handle_get_locations_tree(client: HomeboxClient, withItems: bool = False) -> str:
    """Get Locations as a nested tree structure."""
    params = {"withItems": str(withItems).lower()}
    data = await client.request("GET", "locations/tree", params=params)
    return json.dumps(data, indent=2)

async def handle_get_location(client: HomeboxClient, id: str) -> str:
    """Get full details for a specific location by ID."""
    data = await client.request("GET", f"locations/{id}")
    link = client.get_web_url("location", data["id"])
    
    return f"Location: {data.get('name')}\nLink: {link}\n\n{json.dumps(data, indent=2)}"

@protect_resource(resource_type="locations", action="update")
async def handle_update_location(client: HomeboxClient, id: str, name: str | None = None, description: str | None = None, parentId: str | None = None) -> str:
    """Update an existing location."""
    existing = await client.request("GET", f"locations/{id}")
    payload = existing.copy()
    
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if parentId:
        payload["parentId"] = parentId
    elif "parent" in existing and existing["parent"]:
        payload["parentId"] = existing["parent"]["id"]
        
    data = await client.request("PUT", f"locations/{id}", json=payload)
    return f"Updated Location: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="locations", action="delete")
async def handle_delete_location(client: HomeboxClient, id: str) -> str:
    """Delete a location by ID."""
    await client.request("DELETE", f"locations/{id}")
    return "Deleted Location"

# --- Registration ---

def register_locations_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def list_locations(filterChildren: bool = False) -> str:
        """Get All Locations"""
        return await handle_list_locations(client, filterChildren)

    @mcp.tool()
    async def create_location(name: str, description: str | None = None, parentId: str | None = None) -> str:
        """Create Location"""
        return await handle_create_location(client, name, description, parentId)

    @mcp.tool()
    async def get_locations_tree(withItems: bool = False) -> str:
        """Get Locations Tree"""
        return await handle_get_locations_tree(client, withItems)

    @mcp.tool()
    async def get_location(id: str) -> str:
        """Get Location"""
        return await handle_get_location(client, id)

    @mcp.tool()
    async def update_location(id: str, name: str | None = None, description: str | None = None, parentId: str | None = None) -> str:
        """Update Location"""
        return await handle_update_location(client, id, name, description, parentId)

    @mcp.tool()
    async def delete_location(id: str) -> str:
        """Delete Location"""
        return await handle_delete_location(client, id)
