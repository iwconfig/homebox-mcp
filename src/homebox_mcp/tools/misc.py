import json
import io
import base64
from typing import Any, Union, List
from PIL import Image
from mcp.types import ImageContent
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

# --- Tool Handlers ---

async def handle_get_status(client: HomeboxClient) -> str:
    data = await client.request("GET", "status")
    return json.dumps(data, indent=2)

async def handle_list_currencies(client: HomeboxClient) -> str:
    try:
        data = await client.request("GET", "currencies")
        return json.dumps(data, indent=2)
    except Exception as e:
        if "404" in str(e):
            return "Currency information endpoint not found (404). This might not be supported in this Homebox version."
        raise

async def handle_create_qrcode(client: HomeboxClient, text: str) -> Union[List[ImageContent], str]:
    data = await client.request("GET", "qrcode", params={"data": text})
    # If qrcode returns an image (likely), handle it
    if isinstance(data, bytes):
        b64 = base64.b64encode(data).decode("utf-8")
        return [ImageContent(type="image", data=b64, mimeType="image/png")]
    return f"QR Code Data: {data}"

async def handle_search_product_by_barcode(client: HomeboxClient, barcode: str) -> str:
    try:
        # Source code confirms the key is 'productEAN' for the decoder
        data = await client.request("GET", "products/search-from-barcode", params={"productEAN": barcode})
        if not data:
            return f"No products found for barcode {barcode}"
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error searching product by barcode: {str(e)}"

async def handle_get_label_image(client: HomeboxClient, type: str, id: str, print_label: bool = False) -> List[ImageContent]:
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
    data = await client.request("GET", path, params=params)
    
    if isinstance(data, bytes):
        b64 = base64.b64encode(data).decode("utf-8")
        return [ImageContent(type="image", data=b64, mimeType="image/png")]
    
    raise ValueError(f"Expected image data, but got: {type(data)}")


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
    async def create_qrcode(text: str) -> Any:
        """Create QR Code for a string"""
        return await handle_create_qrcode(client, text)

    @mcp.tool()
    async def search_product_by_barcode(barcode: str) -> str:
        """Search EAN from Barcode"""
        return await handle_search_product_by_barcode(client, barcode)

    @mcp.tool()
    async def get_label_image(type: str, id: str, print_label: bool = False) -> Any:
        """
        Get Label Image.
        Type must be one of: 'item', 'asset', 'location'.
        """
        return await handle_get_label_image(client, type, id, print_label)