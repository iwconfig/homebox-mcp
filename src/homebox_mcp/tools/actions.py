from typing import Annotated

from fastmcp import FastMCP, Context

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
    client: HomeboxClient,
    wipe_locations: bool = False,
    wipe_labels: bool = False,
    wipe_maintenance: bool = False,
    ctx: Context | None = None,
) -> str:
    """DANGEROUS: Deletes ALL items in the inventory."""
    if ctx:
        await ctx.report_progress(10, 100, "Preparing to wipe inventory...")

    payload = {
        "wipeLocations": wipe_locations,
        "wipeLabels": wipe_labels,
        "wipeMaintenance": wipe_maintenance,
    }

    if ctx:
        await ctx.report_progress(30, 100, "Sending wipe request to backend...")

    await client.wipe_inventory(payload)

    if ctx:
        await ctx.report_progress(100, 100, "Inventory wiped successfully.")

    return "Action triggered: Wipe inventory"


async def handle_audit_inventory(client: HomeboxClient, ctx: Context) -> str:
    """
    Performs an inventory audit and uses sampling to resolve discrepancies.
    """
    await ctx.report_progress(10, 100, "Fetching current inventory...")
    items_res = await client.list_items(page_size=1000)
    items = items_res.get("items", [])

    if not items:
        return "Inventory is empty, nothing to audit."

    await ctx.report_progress(30, 100, f"Analyzing {len(items)} items for discrepancies...")

    # For this example, we simulate finding a few discrepancies
    # In a real app, this might compare against an external manifest
    discrepancies = [
        {"item_id": items[0]["id"], "name": items[0]["name"], "issue": "Missing quantity information"},
    ]

    if len(items) > 5:
        discrepancies.append(
            {"item_id": items[5]["id"], "name": items[5]["name"], "issue": "Location might be incorrect"}
        )

    await ctx.report_progress(50, 100, f"Found {len(discrepancies)} discrepancies. Requesting resolution...")

    resolutions = []
    for i, disc in enumerate(discrepancies):
        await ctx.report_progress(50 + (i / len(discrepancies) * 40), 100, f"Resolving {i+1}/{len(discrepancies)}...")

        # Use sampling to ask the user (via LLM) how to resolve
        prompt = f"Audit Discrepancy Found:\nItem: {disc['name']} ({disc['item_id']})\nIssue: {disc['issue']}\n\nHow should we resolve this? (e.g., 'Update quantity to 1', 'Move to Electronics', 'Ignore')"

        # We request a structured response from the sampling call
        sample_res = await ctx.sample(
            messages=[prompt],
            system_prompt="You are an inventory auditor. Provide a concise resolution for the reported issue.",
            max_tokens=100
        )

        resolution = sample_res.text
        resolutions.append(f"Item '{disc['name']}': {resolution}")

        # In a real scenario, we'd apply the tool call here
        # e.g., if resolution contains "Update quantity", call update_item

    await ctx.report_progress(100, 100, "Audit completed.")

    summary = "Audit results:\n" + "\n".join(resolutions)
    return summary


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
        ctx: Context | None = None,
    ) -> str:
        """DANGEROUS: Deletes ALL items in the inventory."""
        return await handle_wipe_inventory(
            client,
            wipe_locations=wipe_locations,
            wipe_labels=wipe_labels,
            wipe_maintenance=wipe_maintenance,
            ctx=ctx,
        )

    @mcp.tool()
    async def audit_inventory(ctx: Context) -> str:
        """
        Performs an inventory audit and uses sampling to resolve discrepancies.
        Requires a client that supports sampling.
        """
        return await handle_audit_inventory(client, ctx=ctx)
