from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient
from ..guardrails import protect_resource

# --- Tool Handlers ---


async def handle_list_labels(client: HomeboxClient) -> list[dict]:
    """Get All Labels."""
    return await client.list_labels()


@protect_resource(resource_type="labels", action="create")
async def handle_create_label(
    client: HomeboxClient, name: str, description: str | None = None, color: str | None = None
) -> dict:
    """Create a new label."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if color:
        payload["color"] = color

    return await client.create_label(payload)


async def handle_get_label(client: HomeboxClient, id: str) -> dict:
    """Get details for a specific label by ID."""
    return await client.get_label(id)


@protect_resource(resource_type="labels", action="update")
async def handle_update_label(
    client: HomeboxClient, id: str, name: str | None = None, description: str | None = None, color: str | None = None
) -> dict:
    """Update an existing label."""
    existing = await client.get_label(id)
    payload = existing.copy()

    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if color:
        payload["color"] = color

    return await client.update_label(id, payload)


@protect_resource(resource_type="labels", action="delete")
async def handle_delete_label(client: HomeboxClient, id: str) -> str:
    """Delete a label by ID."""
    await client.delete_label(id)
    return f"Deleted Label {id}"


# --- Registration ---


def register_labels_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool
    async def list_labels() -> dict:
        """Get All Labels"""
        res = await handle_list_labels(client)
        return {"labels": res}

    @mcp.tool
    async def create_label(
        name: Annotated[str, "Name of the label"],
        description: Annotated[str | None, "Description of the label"] = None,
        color: Annotated[str | None, "Color of the label (hex code)"] = None,
    ) -> dict:
        """Create Label"""
        return await handle_create_label(client, name=name, description=description, color=color)

    @mcp.tool()
    async def get_label(id: Annotated[str, "ID of the label"]) -> dict:
        """Get Label"""
        return await handle_get_label(client, id=id)

    @mcp.tool
    async def update_label(
        id: Annotated[str, "ID of the label"],
        name: Annotated[str | None, "New name of the label"] = None,
        description: Annotated[str | None, "New description of the label"] = None,
        color: Annotated[str | None, "New color of the label (hex code)"] = None,
    ) -> dict:
        """Update Label"""
        return await handle_update_label(client, id=id, name=name, description=description, color=color)

    @mcp.tool()
    async def delete_label(id: Annotated[str, "ID of the label"]) -> str:
        """Delete Label"""
        return await handle_delete_label(client, id=id)
