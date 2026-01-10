from typing import Annotated

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from ..client import HomeboxClient

# --- Tool Handlers ---


async def handle_get_status(client: HomeboxClient) -> dict:
    """Get Homebox application status/info."""
    return await client.get_status()


async def handle_list_currencies(client: HomeboxClient) -> list[dict]:
    """Get all supported currencies."""
    return await client.list_currencies()


async def handle_create_qrcode(client: HomeboxClient, text: str) -> Image:
    """Create QR Code for a string."""
    data = await client.create_qrcode(text)
    return Image(data=data, format="png")


async def handle_search_product_by_barcode(client: HomeboxClient, barcode: str) -> list[dict] | None:
    """Search EAN from Barcode."""
    return await client.search_product_by_barcode(barcode)


async def handle_get_label_image(client: HomeboxClient, id: str, type: str, print_label: bool = False) -> Image:
    """Get Label Image. Type must be one of: 'item', 'asset', 'location'."""
    # Map high-level types to the API paths
    if type == "item":
        api_type = "item"
    elif type == "asset":
        api_type = "assets"
    elif type == "location":
        api_type = "location"
    else:
        raise ValueError(f"Invalid label type: {type}. Must be 'item', 'asset', or 'location'.")

    data = await client.get_label_image(api_type, id, print_label=print_label)
    return Image(data=data, format="png")


# --- Registration ---


def register_misc_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def get_status() -> dict:
        """Get Homebox application status/info"""
        return await handle_get_status(client)

    @mcp.tool(output_schema={"type": "object"})
    async def list_currencies() -> dict:
        """Get all supported currencies"""
        res = await handle_list_currencies(client)
        return {"currencies": res}

    @mcp.tool()
    async def create_qrcode(text: Annotated[str, "Text to encode in the QR code"]) -> Image:
        """Create QR Code for a string"""
        return await handle_create_qrcode(client, text=text)

    @mcp.tool(output_schema={"type": "object"})
    async def search_product_by_barcode(barcode: Annotated[str, "The barcode (EAN) to search for"]) -> dict:
        """Search EAN from Barcode"""
        res = await handle_search_product_by_barcode(client, barcode=barcode)
        return {"products": res}

    @mcp.tool()
    async def get_label_image(
        id: Annotated[str, "ID of the item, asset, or location"],
        type: Annotated[str, "Type of label: 'item', 'asset', or 'location'"],
        print_label: Annotated[bool, "Whether to optimize for printing"] = False,
    ) -> Image:
        """Get Label Image"""
        return await handle_get_label_image(client, id=id, type=type, print_label=print_label)
