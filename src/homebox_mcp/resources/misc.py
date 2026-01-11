import json

from fastmcp import FastMCP

from homebox_mcp.client import HomeboxClient


def register_misc_resources(mcp: FastMCP, client: HomeboxClient):
    """Register miscellaneous resources (User, Status, Reporting)."""

    @mcp.resource("homebox://status", mime_type="application/json")
    async def get_status() -> str:
        """
        Get the Homebox application status and version info.
        URI: homebox://status
        """
        status = await client.get_status()
        return json.dumps(status, indent=2)

    @mcp.resource("homebox://users/self", mime_type="application/json")
    async def get_user_self() -> str:
        """
        Get details about the currently authenticated user.
        URI: homebox://users/self
        """
        user = await client.get_user_self()
        return json.dumps(user, indent=2)

    @mcp.resource("homebox://reporting/bom", mime_type="text/csv")
    async def get_bom() -> str:
        """
        Get the Bill of Materials (BOM) export.
        URI: homebox://reporting/bom
        """
        bom = await client.export_bom()
        # BOM might be CSV or JSON? Client returns whatever the API returns.
        # Check client implementation. 
        # export_bom -> "GET", "reporting/bill-of-materials"
        # API returns CSV text usually.
        # Resource content should be string.
        if isinstance(bom, str):
            return bom
        return json.dumps(bom, indent=2)
