import json
from ..client import HomeboxClient
from fastmcp import FastMCP

# --- Tool Handlers ---

async def handle_query_all_maintenance(client: HomeboxClient, status: str = "both") -> str:
    """Query All Maintenance entries across all items."""
    data = await client.request("GET", "maintenance", params={"status": status})
    return json.dumps(data, indent=2)

async def handle_update_maintenance_entry(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    scheduledDate: str | None = None,
    completedDate: str | None = None,
    cost: float | None = None,
    itemId: str | None = None
) -> str:
    """Update an existing maintenance entry."""
    # Fetch existing entries to find the correct one (maintenance endpoint returns a list)
    all_m = await client.request("GET", "maintenance", params={"status": "both"})
    existing = next((m for m in all_m if m["id"] == id), None)
    
    if not existing:
        return f"Maintenance entry {id} not found"
        
    payload = existing.copy()
    if name:
        payload["name"] = name
    if description:
        payload["description"] = description
    if scheduledDate:
        payload["scheduledDate"] = scheduledDate
    if completedDate:
        payload["completedDate"] = completedDate
    if cost is not None:
        payload["cost"] = str(cost)
    if itemId:
        payload["itemId"] = itemId
        
    data = await client.request("PUT", f"maintenance/{id}", json=payload)
    return f"Updated Maintenance: {json.dumps(data, indent=2)}"

async def handle_delete_maintenance_entry(client: HomeboxClient, id: str) -> str:
    """Delete a maintenance entry by ID."""
    await client.request("DELETE", f"maintenance/{id}")
    return "Deleted Maintenance Entry"

# --- Registration ---

def register_maintenance_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def query_all_maintenance(status: str = "both") -> str:
        """Query All Maintenance entries across all items"""
        return await handle_query_all_maintenance(client, status)

    @mcp.tool()
    async def update_maintenance_entry(
        id: str,
        name: str | None = None,
        description: str | None = None,
        scheduledDate: str | None = None,
        completedDate: str | None = None,
        cost: float | None = None,
        itemId: str | None = None
    ) -> str:
        """Update Maintenance Entry"""
        return await handle_update_maintenance_entry(client, id, name, description, scheduledDate, completedDate, cost, itemId)

    @mcp.tool()
    async def delete_maintenance_entry(id: str) -> str:
        """Delete Maintenance Entry"""
        return await handle_delete_maintenance_entry(client, id)