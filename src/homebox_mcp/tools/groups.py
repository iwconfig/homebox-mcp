from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient

# --- Tool Handlers ---


async def handle_get_group(client: HomeboxClient) -> dict:
    """Get current group information."""
    return await client.get_group()


async def handle_update_group(client: HomeboxClient, name: str | None = None, currency: str | None = None) -> dict:
    """Update current group name or currency."""
    payload = {}
    if name:
        payload["name"] = name
    if currency:
        payload["currency"] = currency

    return await client.update_group(payload)


async def handle_create_group_invitation(client: HomeboxClient, uses: int = 1, expires_at: str | None = None) -> dict:
    """Create a new invitation for the group."""
    payload = {"uses": uses}
    if expires_at:
        payload["expiresAt"] = expires_at

    return await client.create_group_invitation(payload)


async def handle_get_group_statistics(client: HomeboxClient) -> dict:
    """Get overall group statistics."""
    return await client.get_group_statistics()


async def handle_get_label_statistics(client: HomeboxClient) -> dict:
    """Get item counts and values per label."""
    return await client.get_group_statistics_labels()


async def handle_get_location_statistics(client: HomeboxClient) -> dict:
    """Get item counts and values per location."""
    return await client.get_group_statistics_locations()


async def handle_get_purchase_price_statistics(
    client: HomeboxClient, start: str | None = None, end: str | None = None
) -> dict:
    """Get purchase price history within a date range."""
    return await client.get_purchase_price_statistics(start=start, end=end)


async def handle_export_bom(client: HomeboxClient) -> str:
    """Export the Bill of Materials."""
    data = await client.export_bom()
    return str(data)


# --- Registration ---


def register_groups_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool
    async def get_group() -> dict:
        """Get Group Info"""
        return await handle_get_group(client)

    @mcp.tool
    async def update_group(
        name: Annotated[str | None, "New name for the group"] = None,
        currency: Annotated[str | None, "New currency code (e.g. USD, EUR)"] = None,
    ) -> dict:
        """Update Group Info"""
        return await handle_update_group(client, name=name, currency=currency)

    @mcp.tool
    async def create_group_invitation(
        uses: Annotated[int, "Number of times the invitation can be used"] = 1,
        expires_at: Annotated[str | None, "ISO 8601 date when invitation expires"] = None,
    ) -> dict:
        """Create Group Invitation"""
        return await handle_create_group_invitation(client, uses=uses, expires_at=expires_at)

    @mcp.tool
    async def get_group_statistics() -> dict:
        """Get Group Statistics"""
        return await handle_get_group_statistics(client)

    @mcp.tool
    async def get_label_statistics() -> dict:
        """Get Label Statistics"""
        res = await handle_get_label_statistics(client)
        return {"labels": res}

    @mcp.tool
    async def get_location_statistics() -> dict:
        """Get Location Statistics"""
        res = await handle_get_location_statistics(client)
        return {"locations": res}

    @mcp.tool
    async def get_purchase_price_statistics(
        start: Annotated[str | None, "Start date (ISO 8601)"] = None,
        end: Annotated[str | None, "End date (ISO 8601)"] = None,
    ) -> dict:
        """Get Purchase Price Statistics"""
        res = await handle_get_purchase_price_statistics(client, start=start, end=end)
        return {"statistics": res}

    @mcp.tool()
    async def export_bom() -> str:
        """Export Bill of Materials"""
        return await handle_export_bom(client)
