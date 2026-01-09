import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .client import HomeboxClient
from .prompts import register_all_prompts
from .tools import register_all_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("homebox-mcp")

# Initialize Client globally for tool registration
# FastMCP 2.0 tools can also access this via lifespan if needed
client = HomeboxClient()

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """
    Manage the lifecycle of the HomeboxClient.
    Ensures resources are cleaned up when the server shuts down.
    """
    try:
        # Yield the client to make it available in the server context
        yield {"client": client}
    finally:
        # Close the underlying HTTP sessions
        await client.close()

# Initialize FastMCP 2.0
# We provide custom instructions and a lifespan handler
mcp = FastMCP(
    "Homebox",
    lifespan=lifespan,
    instructions="MCP server for Homebox inventory management system",
)

# Register all tools and prompts with the server instance
register_all_tools(mcp, client)
register_all_prompts(mcp)

def main():
    """
    Main entry point for the homebox-mcp server.
    Supports both stdio and SSE transports based on environment variables or CLI arguments.
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    # Allow CLI overrides
    if len(sys.argv) > 1:
        if "sse" in sys.argv:
            transport = "sse"
        elif "stdio" in sys.argv:
            transport = "stdio"

    if transport == "sse":
        logger.info(f"Starting Homebox MCP server over SSE on {host}:{port}")
        logger.info(f"Endpoint: http://{host}:{port}/sse")
        # Run using the built-in starlette/uvicorn SSE transport
        mcp.run(transport="sse", host=host, port=port)
    else:
        # Default to standard I/O transport
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
