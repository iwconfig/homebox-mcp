import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware

from homebox_mcp.client import HomeboxClient
from homebox_mcp.prompts import register_all_prompts
from homebox_mcp.resources import register_all_resources
from homebox_mcp.tools import register_all_tools

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


def _get_dynamic_instructions() -> str:
    """Generate dynamic context for the LLM based on environment state."""
    instructions = [
        "MCP server for Homebox inventory management system",
        "You are an expert inventory manager for Homebox.",
        "Always try to use human-readable names; the server will resolve them to UUIDs using fuzzy matching if needed.",
    ]

    # Add context about guardrails
    readonly = os.getenv("HOMEBOX_READONLY_RESOURCES", "")
    if readonly:
        if "all" in readonly.lower():
            instructions.append("IMPORTANT: The entire inventory is in READ-ONLY mode. Do not attempt to create, update, or delete resources.")
        else:
            instructions.append(f"IMPORTANT: The following resources are READ-ONLY: {readonly}. Do not attempt to modify them.")

    non_deletable = os.getenv("HOMEBOX_NON_DELETABLE_RESOURCES", "")
    if non_deletable:
        instructions.append(f"NOTE: The following resources cannot be deleted: {non_deletable}.")

    # Safety switch info
    if os.getenv("HOMEBOX_ALLOW_WIPE_INVENTORY", "false").lower() != "true":
        instructions.append("The 'wipe_inventory' action is hard-disabled.")

    return "\n".join(instructions)


# Initialize FastMCP 2.0
# We provide custom instructions and a lifespan handler
mcp = FastMCP(
    "Homebox",
    lifespan=lifespan,
    instructions=_get_dynamic_instructions(),
)

# Add Middleware
# Error handling first to catch errors from other middleware/tools
mcp.add_middleware(ErrorHandlingMiddleware())
# Logging to track requests
mcp.add_middleware(LoggingMiddleware())

# Register all tools, prompts and resources with the server instance
register_all_tools(mcp, client)
register_all_prompts(mcp)
register_all_resources(mcp, client)


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
