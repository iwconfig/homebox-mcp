import json
from ..client import HomeboxClient
from fastmcp import FastMCP, Context

# --- Tool Handlers ---

async def handle_list_notifiers(client: HomeboxClient) -> str:
    data = await client.request("GET", "notifiers")
    return json.dumps(data, indent=2)

async def handle_create_notifier(client: HomeboxClient, name: str, url: str, isActive: bool = True) -> str:
    payload = {"name": name, "url": url, "isActive": isActive}
    data = await client.request("POST", "notifiers", json=payload)
    return f"Created Notifier: {json.dumps(data, indent=2)}"

async def handle_test_notifier(client: HomeboxClient, url: str) -> str:
    try:
        # Body field 'url' is required for validation
        await client.request("POST", "notifiers/test", json={"url": url})
        return "Notifier test signal sent successfully"
    except Exception as e:
        return f"Error testing notifier: {str(e)}"

async def handle_update_notifier(client: HomeboxClient, id: str, name: str = None, url: str = None, isActive: bool = None) -> str:
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

async def handle_delete_notifier(client: HomeboxClient, id: str) -> str:
    await client.request("DELETE", f"notifiers/{id}")
    return "Deleted Notifier"


# --- Registration ---

def register_notifiers_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_notifiers() -> str:
        """Get Notifiers"""
        return await handle_list_notifiers(client)

    @mcp.tool()
    async def create_notifier(name: str, url: str, isActive: bool = True) -> str:
        """Create Notifier"""
        return await handle_create_notifier(client, name, url, isActive)

    @mcp.tool()
    async def test_notifier(url: str) -> str:
        """Test Notifier"""
        return await handle_test_notifier(client, url)

    @mcp.tool()
    async def update_notifier(id: str, name: str = None, url: str = None, isActive: bool = None) -> str:
        """Update Notifier"""
        return await handle_update_notifier(client, id, name, url, isActive)

    @mcp.tool()
    async def delete_notifier(id: str) -> str:
        """Delete a Notifier"""
        return await handle_delete_notifier(client, id)