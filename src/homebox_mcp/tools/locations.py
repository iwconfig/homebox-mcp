import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_locations_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_locations(filterChildren: bool = False) -> str:
        """Get All Locations"""
        params = {"filterChildren": str(filterChildren).lower()}
        data = await client.request("GET", "locations", params=params)
        
        output = f"Found {len(data)} locations:\n\n"
        for loc in data:
            link = client.get_web_url("location", loc["id"])
            output += f"- [{loc.get('name')}]({link}) (ID: {loc.get('id')}) - Items: {loc.get('itemCount', 0)}\n"
        return output

    @mcp.tool()
    async def create_location(name: str, description: str = None, parentId: str = None) -> str:
        """Create Location"""
        payload = {"name": name}
        if description: payload["description"] = description
        if parentId: payload["parentId"] = parentId
        data = await client.request("POST", "locations", json=payload)
        return f"Created Location: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_locations_tree(withItems: bool = False) -> str:
        """Get Locations Tree"""
        params = {"withItems": str(withItems).lower()}
        data = await client.request("GET", "locations/tree", params=params)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_location(id: str) -> str:
        """Get Location"""
        data = await client.request("GET", f"locations/{id}")
        link = client.get_web_url("location", data["id"])
        return f"Location: {data.get('name')}\nLink: {link}\n\n{json.dumps(data, indent=2)}"

    @mcp.tool()
    async def update_location(id: str, name: str = None, description: str = None, parentId: str = None) -> str:
        """Update Location"""
        existing = await client.request("GET", f"locations/{id}")
        payload = existing.copy()
        if name: payload["name"] = name
        if description: payload["description"] = description
        if parentId: payload["parentId"] = parentId
        elif "parent" in existing and existing["parent"]:
            payload["parentId"] = existing["parent"]["id"]

        data = await client.request("PUT", f"locations/{id}", json=payload)
        return f"Updated Location: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def delete_location(id: str) -> str:
        """Delete Location"""
        await client.request("DELETE", f"locations/{id}")
        return "Deleted Location"
