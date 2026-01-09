import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator
import uvicorn
from fastmcp import FastMCP
from .client import HomeboxClient
from .tools import register_all_tools
from .prompts import register_all_prompts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("homebox-mcp")

# Initialize Client
client = HomeboxClient()

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the lifecycle of the HomeboxClient."""
    try:
        yield {"client": client}
    finally:
        await client.close()

# Initialize FastMCP 2.0
mcp = FastMCP(
    "Homebox",
    lifespan=lifespan,
    instructions="MCP server for Homebox inventory management system",
)

# Register tools and prompts
register_all_tools(mcp, client)
register_all_prompts(mcp)

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
        logger.info(f"Starting Homebox MCP server over SSE on {host}:{port}")
        logger.info(f"Endpoint: http://{host}:{port}/sse")
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
