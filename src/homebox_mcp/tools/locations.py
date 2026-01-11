from typing import Annotated

from fastmcp import FastMCP, Context

from ..client import HomeboxClient
from ..guardrails import protect_resource
from ._helpers import fuzzy_resolve_id

# --- Tool Handlers ---


async def handle_list_locations(client: HomeboxClient, filter_children: bool = False) -> list[dict]:
    """Get All Locations."""
    return await client.list_locations(filter_children=filter_children)


@protect_resource(resource_type="locations", action="create")
async def handle_create_location(
    client: HomeboxClient,
    name: str,
    description: str | None = None,
    parent_id: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Create a new location."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if parent_id:
        payload["parentId"] = await fuzzy_resolve_id(client, "locations", parent_id, ctx, name)

    return await client.create_location(payload)


async def handle_get_locations_tree(client: HomeboxClient, with_items: bool = False) -> list[dict]:
    """Get Locations as a nested tree structure."""
    return await client.get_locations_tree(with_items=with_items)


async def handle_get_location(client: HomeboxClient, id: str) -> dict:
    """Get full details for a specific location by ID."""
    return await client.get_location(id)


@protect_resource(resource_type="locations", action="update")
async def handle_update_location(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    parent_id: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Update an existing location."""
    existing = await client.get_location(id)
    payload = existing.copy()

    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    
    target_name = name or existing.get("name")
    if parent_id:
        payload["parentId"] = await fuzzy_resolve_id(client, "locations", parent_id, ctx, target_name)
    elif "parent" in existing and existing["parent"]:
        payload["parentId"] = existing["parent"]["id"]

    return await client.update_location(id, payload)


@protect_resource(resource_type="locations", action="delete")
async def handle_delete_location(client: HomeboxClient, id: str) -> str:
    """Delete a location by ID."""
    await client.delete_location(id)
    return f"Deleted Location {id}"


# --- Registration ---


def register_locations_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool
    async def list_locations(filter_children: Annotated[bool, "Whether to filter children"] = False) -> dict:
        """Get All Locations"""
        res = await handle_list_locations(client, filter_children=filter_children)
        return {"locations": res}

    @mcp.tool
    async def create_location(
        name: Annotated[str, "Name of the location"],
        description: Annotated[str | None, "Description of the location"] = None,
        parent_id: Annotated[str | None, "ID of the parent location"] = None,
        ctx: Context | None = None,
    ) -> dict:
        """Create Location"""
        return await handle_create_location(client, name=name, description=description, parent_id=parent_id, ctx=ctx)

    @mcp.tool
    async def get_locations_tree(with_items: Annotated[bool, "Whether to include items in the tree"] = False) -> dict:
        """Get Locations Tree"""
        res = await handle_get_locations_tree(client, with_items=with_items)
        return {"tree": res}

    @mcp.tool()
    async def get_location(id: Annotated[str, "ID of the location"]) -> dict:
        """Get Location"""
        return await handle_get_location(client, id=id)

    @mcp.tool
    async def update_location(
        id: Annotated[str, "ID of the location"],
        name: Annotated[str | None, "New name of the location"] = None,
        description: Annotated[str | None, "New description of the location"] = None,
        parent_id: Annotated[str | None, "New parent ID of the location"] = None,
        ctx: Context | None = None,
    ) -> dict:
        """Update Location"""
        return await handle_update_location(
            client, id=id, name=name, description=description, parent_id=parent_id, ctx=ctx
        )

    @mcp.tool()
    async def delete_location(id: Annotated[str, "ID of the location"]) -> str:
        """Delete Location"""
        return await handle_delete_location(client, id=id)
