import json
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_misc_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def get_status() -> str:
        """Get Homebox application status/info"""
        data = await client.request("GET", "status")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def list_currencies() -> str:
        """Get all supported currencies"""
        try:
            data = await client.request("GET", "currencies")
            return json.dumps(data, indent=2)
        except Exception as e:
            if "404" in str(e):
                return "Currency information endpoint not found (404). This might not be supported in this Homebox version."
            raise

    @mcp.tool()
    async def create_qrcode(text: str) -> str:
        """Create QR Code for a string"""
        data = await client.request("GET", "qrcode", params={"data": text})
        return f"QR Code Data: {data}"

    @mcp.tool()
    async def search_product_by_barcode(barcode: str) -> str:
        """Search EAN from Barcode"""
        try:
            # Source code confirms the key is 'productEAN' for the decoder
            data = await client.request("GET", "products/search-from-barcode", params={"productEAN": barcode})
            if not data:
                return f"No products found for barcode {barcode}"
            return json.dumps(data, indent=2)
        except Exception as e:
            return f"Error searching product by barcode: {str(e)}"

    @mcp.tool()
    async def get_label_image(type: str, id: str, print_label: bool = False) -> str:
        """
        Get Label Image (Base64).
        Type must be one of: 'item', 'asset', 'location'.
        """
        if type not in ["item", "asset", "location"]:
            return "Error: Type must be 'item', 'asset', or 'location'"
        
        path = ""
        if type == "asset":
            path = f"labelmaker/assets/{id}"
        elif type == "item":
            path = f"labelmaker/item/{id}"
        elif type == "location":
            path = f"labelmaker/location/{id}"
            
        params = {"print": str(print_label).lower()}
        data = await client.request("GET", path, params=params)
        return f"Label Image (Base64): {data}"
