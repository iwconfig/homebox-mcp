import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_groups_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def get_group() -> str:
        """Get Group Info"""
        data = await client.request("GET", "groups")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_group(name: str = None, currency: str = None) -> str:
        """Update Group Info"""
        payload = {}
        if name: payload["name"] = name
        if currency: payload["currency"] = currency
        data = await client.request("PUT", "groups", json=payload)
        return f"Updated Group: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def create_group_invitation(email: str, role: str = "user") -> str:
        """Create Group Invitation"""
        data = await client.request("POST", "groups/invitations", json={"email": email, "role": role})
        return f"Created Invitation: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_group_statistics() -> str:
        """Get Group Statistics"""
        data = await client.request("GET", "groups/statistics")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_label_statistics() -> str:
        """Get Label Statistics"""
        data = await client.request("GET", "groups/statistics/labels")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_location_statistics() -> str:
        """Get Location Statistics"""
        data = await client.request("GET", "groups/statistics/locations")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_purchase_price_statistics(start: str = None, end: str = None) -> str:
        """Get Purchase Price Statistics"""
        params = {}
        if start: params["start"] = start
        if end: params["end"] = end
        data = await client.request("GET", "groups/statistics/purchase-price", params=params)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def export_bom() -> str:
        """Export Bill of Materials"""
        data = await client.request("GET", "reporting/bill-of-materials")
        return str(data)
