import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_notifiers_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_notifiers() -> str:
        """Get Notifiers"""
        data = await client.request("GET", "notifiers")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def create_notifier(name: str, url: str, isActive: bool = True) -> str:
        """Create Notifier"""
        payload = {"name": name, "url": url, "isActive": isActive}
        data = await client.request("POST", "notifiers", json=payload)
        return f"Created Notifier: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def test_notifier(url: str) -> str:
        """Test Notifier"""
        await client.request("POST", "notifiers/test", params={"url": url})
        return "Notifier test sent"

    @mcp.tool()
    async def update_notifier(id: str, name: str = None, url: str = None, isActive: bool = None) -> str:
        """Update Notifier"""
        existing_list = await client.request("GET", "notifiers")
        notifier = next((n for n in existing_list if n["id"] == id), None)
        if not notifier:
            return f"Notifier {id} not found"
        
        payload = notifier.copy()
        if name: payload["name"] = name
        if url: payload["url"] = url
        if isActive is not None: payload["isActive"] = isActive
        
        data = await client.request("PUT", f"notifiers/{id}", json=payload)
        return f"Updated Notifier: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def delete_notifier(id: str) -> str:
        """Delete a Notifier"""
        await client.request("DELETE", f"notifiers/{id}")
        return "Deleted Notifier"
