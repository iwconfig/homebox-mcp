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
    async def get_currency() -> str:
        """Get currency information"""
        data = await client.request("GET", "currency")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def create_qrcode(text: str) -> str:
        """Create QR Code for a string"""
        data = await client.request("GET", "qrcode", params={"q": text})
        return f"QR Code Data: {data}"

    @mcp.tool()
    async def search_product_by_barcode(barcode: str) -> str:
        """Search EAN from Barcode"""
        data = await client.request("GET", "products/search-from-barcode", params={"barcode": barcode})
        return json.dumps(data, indent=2)
