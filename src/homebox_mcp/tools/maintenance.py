import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_maintenance_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def query_all_maintenance(status: str = "both") -> str:
        """Query All Maintenance entries across all items"""
        data = await client.request("GET", "maintenance", params={"status": status})
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_maintenance_entry(
        id: str,
        name: str = None,
        description: str = None,
        scheduledDate: str = None,
        completedDate: str = None,
        cost: float = None,
        itemId: str = None
    ) -> str:
        """Update Maintenance Entry"""
        all_m = await client.request("GET", "maintenance")
        existing = next((m for m in all_m if m["id"] == id), None)
        if not existing:
            return f"Maintenance entry {id} not found"
            
        payload = existing.copy()
        if name: payload["name"] = name
        if description: payload["description"] = description
        if scheduledDate: payload["scheduledDate"] = scheduledDate
        if completedDate: payload["completedDate"] = completedDate
        if cost is not None: payload["cost"] = cost
        if itemId: payload["itemId"] = itemId
            
        data = await client.request("PUT", f"maintenance/{id}", json=payload)
        return f"Updated Maintenance: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def delete_maintenance_entry(id: str) -> str:
        """Delete Maintenance Entry"""
        await client.request("DELETE", f"maintenance/{id}")
        return "Deleted Maintenance Entry"
