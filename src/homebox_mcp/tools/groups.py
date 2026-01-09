import json
from ..client import HomeboxClient
from fastmcp import FastMCP

# --- Tool Handlers ---

async def handle_get_group(client: HomeboxClient) -> str:
    """Get current group information."""
    data = await client.request("GET", "groups")
    return json.dumps(data, indent=2)

async def handle_update_group(client: HomeboxClient, name: str | None = None, currency: str | None = None) -> str:
    """Update current group name or currency."""
    payload = {}
    if name:
        payload["name"] = name
    if currency:
        payload["currency"] = currency
        
    data = await client.request("PUT", "groups", json=payload)
    return f"Updated Group: {json.dumps(data, indent=2)}"

async def handle_create_group_invitation(client: HomeboxClient, uses: int = 1, expiresAt: str | None = None) -> str:
    """Create a new invitation for the group."""
    payload = {"uses": uses}
    if expiresAt:
        payload["expiresAt"] = expiresAt
        
    data = await client.request("POST", "groups/invitations", json=payload)
    return f"Created Invitation: {json.dumps(data, indent=2)}"

async def handle_get_group_statistics(client: HomeboxClient) -> str:
    """Get overall group statistics."""
    data = await client.request("GET", "groups/statistics")
    return json.dumps(data, indent=2)

async def handle_get_label_statistics(client: HomeboxClient) -> str:
    """Get item counts and values per label."""
    data = await client.request("GET", "groups/statistics/labels")
    return json.dumps(data, indent=2)

async def handle_get_location_statistics(client: HomeboxClient) -> str:
    """Get item counts and values per location."""
    data = await client.request("GET", "groups/statistics/locations")
    return json.dumps(data, indent=2)

async def handle_get_purchase_price_statistics(client: HomeboxClient, start: str | None = None, end: str | None = None) -> str:
    """Get purchase price history within a date range."""
    params = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
        
    data = await client.request("GET", "groups/statistics/purchase-price", params=params)
    return json.dumps(data, indent=2)

async def handle_export_bom(client: HomeboxClient) -> str:
    """Export the Bill of Materials."""
    data = await client.request("GET", "reporting/bill-of-materials")
    return str(data)

# --- Registration ---

def register_groups_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def get_group() -> str:
        """Get Group Info"""
        return await handle_get_group(client)

    @mcp.tool()
    async def update_group(name: str | None = None, currency: str | None = None) -> str:
        """Update Group Info"""
        return await handle_update_group(client, name, currency)

    @mcp.tool()
    async def create_group_invitation(uses: int = 1, expiresAt: str | None = None) -> str:
        """Create Group Invitation"""
        return await handle_create_group_invitation(client, uses, expiresAt)

    @mcp.tool()
    async def get_group_statistics() -> str:
        """Get Group Statistics"""
        return await handle_get_group_statistics(client)

    @mcp.tool()
    async def get_label_statistics() -> str:
        """Get Label Statistics"""
        return await handle_get_label_statistics(client)

    @mcp.tool()
    async def get_location_statistics() -> str:
        """Get Location Statistics"""
        return await handle_get_location_statistics(client)

    @mcp.tool()
    async def get_purchase_price_statistics(start: str | None = None, end: str | None = None) -> str:
        """Get Purchase Price Statistics"""
        return await handle_get_purchase_price_statistics(client, start, end)

    @mcp.tool()
    async def export_bom() -> str:
        """Export Bill of Materials"""
        return await handle_export_bom(client)