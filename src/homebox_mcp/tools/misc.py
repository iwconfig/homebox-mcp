import json
from ..client import HomeboxClient
from fastmcp import FastMCP
from fastmcp.utilities.types import Image

# --- Tool Handlers ---

async def handle_get_status(client: HomeboxClient) -> str:
    """Get the status and version information of the Homebox instance."""
    data = await client.request("GET", "status")
    return json.dumps(data, indent=2)

async def handle_list_currencies(client: HomeboxClient) -> str:
    """Retrieve all supported currencies from the backend."""
    try:
        data = await client.request("GET", "currencies")
        return json.dumps(data, indent=2)
    except Exception as e:
        if "404" in str(e):
            return "Currency information endpoint not found (404). This might not be supported in this Homebox version."
        raise

async def handle_create_qrcode(client: HomeboxClient, text: str) -> Image:
    """Generate a QR code for the provided text. Returns a native Image."""
    data = await client.request("GET", "qrcode", params={"data": text}, return_bytes=True)
    return Image(data=data, format="png")

async def handle_search_product_by_barcode(client: HomeboxClient, barcode: str) -> str:
    """Look up product information using an EAN/Barcode."""
    try:
        # Note: Backend expects 'productEAN' despite some documentation saying 'data'
        data = await client.request("GET", "products/search-from-barcode", params={"productEAN": barcode})
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error searching product by barcode: {str(e)}"

async def handle_get_label_image(client: HomeboxClient, type: str, id: str, print_label: bool = False) -> Image:
    """
    Generate a printable label for an item, asset, or location.
    Returns a native Image.
    """
    if type not in ["item", "asset", "location"]:
        raise ValueError("Error: Type must be 'item', 'asset', or 'location'")
    
    path = ""
    if type == "asset":
        path = f"labelmaker/assets/{id}"
    elif type == "item":
        path = f"labelmaker/item/{id}"
    elif type == "location":
        path = f"labelmaker/location/{id}"
        
    params = {"print": str(print_label).lower()}
    data = await client.request("GET", path, params=params, return_bytes=True)
    
    return Image(data=data, format="png")

# --- Registration ---

def register_misc_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def get_status() -> str:
        """Get Homebox application status/info"""
        return await handle_get_status(client)

    @mcp.tool()
    async def list_currencies() -> str:
        """Get all supported currencies"""
        return await handle_list_currencies(client)

    @mcp.tool()
    async def create_qrcode(text: str) -> Image:
        """Create QR Code for a string"""
        return await handle_create_qrcode(client, text)

    @mcp.tool()
    async def search_product_by_barcode(barcode: str) -> str:
        """Search EAN from Barcode"""
        return await handle_search_product_by_barcode(client, barcode)

    @mcp.tool()
    async def get_label_image(type: str, id: str, print_label: bool = False) -> Image:
        """
        Get Label Image.
        Type must be one of: 'item', 'asset', 'location'.
        """
        return await handle_get_label_image(client, type, id, print_label)
