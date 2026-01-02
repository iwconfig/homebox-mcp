import logging
import os
import sys
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import Settings
from mcp.server.transport_security import TransportSecuritySettings
from .client import HomeboxClient
from .tools import register_all_tools
from .resources import register_all_resources
from .prompts import register_prompts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("homebox-mcp")

# Disable DNS rebinding protection
transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# Initialize FastMCP with explicit settings to ensure transport_security is respected
mcp = FastMCP(
    "Homebox",
    transport_security=transport_security
)

# Force it on the internal settings object as well just in case
if hasattr(mcp, "settings"):
    mcp.settings.transport_security = transport_security

# Initialize Client
client = HomeboxClient()

# This will trigger the registration of tools to the mcp instance
register_all_tools(mcp, client)
register_all_resources(mcp, client)
register_prompts(mcp)

def main():
    """Main entry point for the homebox-mcp server."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    if len(sys.argv) > 1:
        if "sse" in sys.argv:
            transport = "sse"
        elif "stdio" in sys.argv:
            transport = "stdio"

    if transport == "sse":
        print(f"Starting Homebox MCP server over SSE on {host}:{port}", file=sys.stderr)
        print(f"Endpoint: http://{host}:{port}/sse", file=sys.stderr)
        # sse_app() uses mcp.settings internally to create SseServerTransport
        uvicorn.run(mcp.sse_app(), host=host, port=port)
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
