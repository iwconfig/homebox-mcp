import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_templates_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_templates() -> str:
        """Get All Item Templates"""
        data = await client.request("GET", "templates")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def create_template(name: str, description: str = None, itemData: dict = None) -> str:
        """Create Item Template"""
        payload = {"name": name}
        if description: payload["description"] = description
        if itemData: payload["itemData"] = itemData
        data = await client.request("POST", "templates", json=payload)
        return f"Created Template: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_template(id: str) -> str:
        """Get Item Template"""
        data = await client.request("GET", f"templates/{id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_template(id: str, name: str = None, description: str = None, itemData: dict = None) -> str:
        """Update Item Template"""
        existing = await client.request("GET", f"templates/{id}")
        payload = existing.copy()
        if name: payload["name"] = name
        if description: payload["description"] = description
        if itemData: payload["itemData"] = itemData
        data = await client.request("PUT", f"templates/{id}", json=payload)
        return f"Updated Template: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def delete_template(id: str) -> str:
        """Delete Item Template"""
        await client.request("DELETE", f"templates/{id}")
        return "Deleted Template"

    @mcp.tool()
    async def create_item_from_template(id: str, locationId: str = None, parentId: str = None, quantity: int = 1) -> str:
        """Create Item from Template"""
        payload = {"locationId": locationId, "parentId": parentId, "quantity": quantity}
        data = await client.request("POST", f"templates/{id}/create-item", json=payload)
        return f"Created Item: {json.dumps(data, indent=2)}"
