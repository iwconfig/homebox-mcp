from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient
from ..guardrails import protect_resource

# --- Tool Handlers ---


async def handle_create_missing_thumbnails(client: HomeboxClient) -> str:
    """Creates thumbnails for items that are missing them."""
    await client.create_missing_thumbnails()
    return "Action triggered: Create missing thumbnails"


async def handle_ensure_asset_ids(client: HomeboxClient) -> str:
    """Ensures all items in the database have an asset ID."""
    await client.ensure_asset_ids()
    return "Action triggered: Ensure asset IDs"


async def handle_ensure_import_refs(client: HomeboxClient) -> str:
    """Ensures all items in the database have an import ref."""
    await client.ensure_import_refs()
    return "Action triggered: Ensure import refs"


async def handle_set_primary_photos(client: HomeboxClient) -> str:
    """Sets the first photo of each item as the primary photo."""
    await client.set_primary_photos()
    return "Action triggered: Set primary photos"


async def handle_zero_item_time_fields(client: HomeboxClient) -> str:
    """Resets all item date fields to the beginning of the day (Go zero time)."""
    await client.zero_item_time_fields()
    return "Action triggered: Zero item time fields"


@protect_resource(resource_type="inventory", action="delete")
async def handle_wipe_inventory(
    client: HomeboxClient, wipe_locations: bool = False, wipe_labels: bool = False, wipe_maintenance: bool = False
) -> str:
    """DANGEROUS: Deletes ALL items in the inventory."""
    payload = {
        "wipeLocations": wipe_locations,
        "wipeLabels": wipe_labels,
        "wipeMaintenance": wipe_maintenance
    }
    await client.wipe_inventory(payload)
    return "Action triggered: Wipe inventory"


# --- Registration ---


def register_actions_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def create_missing_thumbnails() -> str:
        """Creates thumbnails for items that are missing them"""
        return await handle_create_missing_thumbnails(client)

    @mcp.tool()
    async def ensure_asset_ids() -> str:
        """Ensures all items in the database have an asset ID"""
        return await handle_ensure_asset_ids(client)

    @mcp.tool()
    async def ensure_import_refs() -> str:
        """Ensures all items in the database have an import ref"""
        return await handle_ensure_import_refs(client)

    @mcp.tool()
    async def set_primary_photos() -> str:
        """Sets the first photo of each item as the primary photo"""
        return await handle_set_primary_photos(client)

    @mcp.tool()
    async def zero_item_time_fields() -> str:
        """Resets all item date fields to the beginning of the day"""
        return await handle_zero_item_time_fields(client)

    @mcp.tool()
    async def wipe_inventory(
        wipe_locations: Annotated[bool, "Whether to also delete all locations"] = False,
        wipe_labels: Annotated[bool, "Whether to also delete all labels"] = False,
        wipe_maintenance: Annotated[bool, "Whether to also delete all maintenance logs"] = False,
    ) -> str:
        """DANGEROUS: Deletes ALL items in the inventory."""
        return await handle_wipe_inventory(
            client, wipe_locations=wipe_locations, wipe_labels=wipe_labels, wipe_maintenance=wipe_maintenance
        )
