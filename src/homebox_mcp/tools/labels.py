import json
from ..client import HomeboxClient
from ..guardrails import protect_resource
from fastmcp import FastMCP, Context

# --- Tool Handlers ---

async def handle_list_labels(client: HomeboxClient) -> str:
    data = await client.request("GET", "labels")
    output = f"Found {len(data)} labels:\n\n"
    for label in data:
        link = client.get_web_url("label", label["id"])
        output += f"- [{label.get('name')}]({link}) (ID: {label.get('id')})\n"
    return output

@protect_resource(resource_type="labels", action="create")
async def handle_create_label(client: HomeboxClient, name: str, description: str = None, color: str = None) -> str:
    payload = {"name": name}
    if description: payload["description"] = description
    if color: payload["color"] = color
    data = await client.request("POST", "labels", json=payload)
    return f"Created Label: {json.dumps(data, indent=2)}"

async def handle_get_label(client: HomeboxClient, id: str) -> str:
    data = await client.request("GET", f"labels/{id}")
    return json.dumps(data, indent=2)

@protect_resource(resource_type="labels", action="update")
async def handle_update_label(client: HomeboxClient, id: str, name: str = None, description: str = None, color: str = None) -> str:
    existing = await client.request("GET", f"labels/{id}")
    payload = existing.copy()
    if name: payload["name"] = name
    if description: payload["description"] = description
    if color: payload["color"] = color
    data = await client.request("PUT", f"labels/{id}", json=payload)
    return f"Updated Label: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="labels", action="delete")
async def handle_delete_label(client: HomeboxClient, id: str) -> str:
    await client.request("DELETE", f"labels/{id}")
    return "Deleted Label"


# --- Registration ---

def register_labels_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_labels() -> str:
        """Get All Labels"""
        return await handle_list_labels(client)

    @mcp.tool()
    async def create_label(name: str, description: str = None, color: str = None) -> str:
        """Create Label"""
        return await handle_create_label(client, name, description, color)

    @mcp.tool()
    async def get_label(id: str) -> str:
        """Get Label"""
        return await handle_get_label(client, id)

    @mcp.tool()
    async def update_label(id: str, name: str = None, description: str = None, color: str = None) -> str:
        """Update Label"""
        return await handle_update_label(client, id, name, description, color)

    @mcp.tool()
    async def delete_label(id: str) -> str:
        """Delete Label"""
        return await handle_delete_label(client, id)
