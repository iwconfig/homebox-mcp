import json
from ..client import HomeboxClient
from ..guardrails import protect_resource
from mcp.server.fastmcp import FastMCP

def register_labels_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_labels() -> str:
        """Get All Labels"""
        data = await client.request("GET", "labels")
        output = f"Found {len(data)} labels:\n\n"
        for label in data:
            link = client.get_web_url("label", label["id"])
            output += f"- [{label.get('name')}]({link}) (ID: {label.get('id')})\n"
        return output

    @mcp.tool()
    @protect_resource(resource_type="labels", action="create")
    async def create_label(name: str, description: str = None, color: str = None) -> str:
        """Create Label"""
        payload = {"name": name}
        if description: payload["description"] = description
        if color: payload["color"] = color
        data = await client.request("POST", "labels", json=payload)
        return f"Created Label: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_label(id: str) -> str:
        """Get Label"""
        data = await client.request("GET", f"labels/{id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    @protect_resource(resource_type="labels", action="update")
    async def update_label(id: str, name: str = None, description: str = None, color: str = None) -> str:
        """Update Label"""
        existing = await client.request("GET", f"labels/{id}")
        payload = existing.copy()
        if name: payload["name"] = name
        if description: payload["description"] = description
        if color: payload["color"] = color
        data = await client.request("PUT", f"labels/{id}", json=payload)
        return f"Updated Label: {json.dumps(data, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="labels", action="delete")
    async def delete_label(id: str) -> str:
        """Delete Label"""
        await client.request("DELETE", f"labels/{id}")
        return "Deleted Label"