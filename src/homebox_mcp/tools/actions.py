import json
import os
from ..client import HomeboxClient
from ..guardrails import protect_resource, check_user_protection
from fastmcp import FastMCP

# --- Tool Handlers (Logic) ---

@protect_resource(resource_type="inventory", action="delete")
async def handle_wipe_inventory(client: HomeboxClient, wipe_labels: bool = False, wipe_locations: bool = False, wipe_maintenance: bool = False) -> str:
    """
    Logic for wiping the entire inventory.
    Requires safety switch and checks for protected accounts.
    """
    # 1. Safety Switch: Must be explicitly enabled via environment
    if os.getenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "").lower() != "true":
        raise ValueError("Safety Lock: 'wipe_inventory' is disabled by default. Set HOMEBOX_ALLOW_WIPE_INVENTORY=true to enable.")
        
    # 2. Guardrail: Ensure current user is not protected
    current_user = await client.request("GET", "users/self")
    check_user_protection(current_user.get("item", {}), "wipe_inventory")
    
    payload = {
        "wipeLabels": wipe_labels,
        "wipeLocations": wipe_locations,
        "wipeMaintenance": wipe_maintenance
    }
    
    data = await client.request("POST", "actions/wipe-inventory", json=payload)
    return json.dumps(data, indent=2)

async def handle_create_missing_thumbnails(client: HomeboxClient) -> str:
    """Trigger background job to create thumbnails for items that lack them."""
    data = await client.request("POST", "actions/create-missing-thumbnails")
    return json.dumps(data, indent=2)

async def handle_ensure_asset_ids(client: HomeboxClient) -> str:
    """Ensure all items have a unique asset ID assigned."""
    data = await client.request("POST", "actions/ensure-asset-ids")
    return json.dumps(data, indent=2)

async def handle_ensure_import_refs(client: HomeboxClient) -> str:
    """Generate missing import references for existing items."""
    data = await client.request("POST", "actions/ensure-import-refs")
    return json.dumps(data, indent=2)

async def handle_set_primary_photos(client: HomeboxClient) -> str:
    """Ensure every item has a primary photo set if attachments exist."""
    data = await client.request("POST", "actions/set-primary-photos")
    return json.dumps(data, indent=2)

async def handle_zero_item_time_fields(client: HomeboxClient) -> str:
    """Reset the time component of item date fields to the start of the day."""
    data = await client.request("POST", "actions/zero-item-time-fields")
    return json.dumps(data, indent=2)

# --- Registration ---

def register_actions_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def wipe_inventory(wipe_labels: bool = False, wipe_locations: bool = False, wipe_maintenance: bool = False) -> str:
        """
        DANGEROUS: Deletes ALL items in the inventory.
        
        REQUIRED: 'HOMEBOX_ALLOW_WIPE_INVENTORY=true' environment variable must be set.
        
        Optionally wipes labels, locations, and maintenance records.
        This action is blocked if 'inventory' is in HOMEBOX_READONLY_RESOURCES 
        or HOMEBOX_NON_DELETABLE_RESOURCES.
        """
        return await handle_wipe_inventory(client, wipe_labels, wipe_locations, wipe_maintenance)

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
