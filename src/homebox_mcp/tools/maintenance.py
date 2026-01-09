from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient

# --- Tool Handlers ---

async def handle_query_all_maintenance(client: HomeboxClient, status: str = "both") -> list[dict]:
    """Query All Maintenance entries across all items."""
    return await client.request("GET", "maintenance", params={"status": status})

async def handle_update_maintenance_entry(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    scheduled_date: str | None = None,
    completed_date: str | None = None,
    cost: float | None = None,
    item_id: str | None = None
) -> dict:
    """Update an existing maintenance entry."""
    all_m = await client.request("GET", "maintenance", params={"status": "both"})
    existing = next((m for m in all_m if m["id"] == id), None)

    if not existing:
        raise ValueError(f"Maintenance entry {id} not found")

    payload = existing.copy()
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if scheduled_date:
        payload["scheduledDate"] = scheduled_date
    if completed_date:
        payload["completedDate"] = completed_date
    if cost is not None:
        payload["cost"] = str(cost)
    if item_id:
        payload["itemId"] = item_id

    return await client.request("PUT", f"maintenance/{id}", json=payload)

async def handle_delete_maintenance_entry(client: HomeboxClient, id: str) -> str:
    """Delete a maintenance entry by ID."""
    await client.request("DELETE", f"maintenance/{id}")
    return f"Deleted Maintenance Entry {id}"

# --- Registration ---

def register_maintenance_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def query_all_maintenance(
        status: Annotated[str, "Filter by status: 'completed', 'scheduled', or 'both'"] = "both"
    ) -> dict:
        """Query All Maintenance entries across all items"""
        res = await handle_query_all_maintenance(client, status=status)
        return {"maintenance": res}

    @mcp.tool(output_schema={"type": "object"})
    async def update_maintenance_entry(
        id: Annotated[str, "ID of the maintenance entry"],
        name: Annotated[str | None, "New name for the entry"] = None,
        description: Annotated[str | None, "New description for the entry"] = None,
        scheduled_date: Annotated[str | None, "New ISO 8601 scheduled date"] = None,
        completed_date: Annotated[str | None, "New ISO 8601 completion date"] = None,
        cost: Annotated[float | None, "New cost"] = None,
        item_id: Annotated[str | None, "New associated item ID"] = None
    ) -> dict:
        """Update Maintenance Entry"""
        return await handle_update_maintenance_entry(
            client, id=id, name=name, description=description,
            scheduled_date=scheduled_date, completed_date=completed_date,
            cost=cost, item_id=item_id
        )

    @mcp.tool()
    async def delete_maintenance_entry(
        id: Annotated[str, "ID of the maintenance entry"]
    ) -> str:
        """Delete Maintenance Entry"""
        return await handle_delete_maintenance_entry(client, id=id)
