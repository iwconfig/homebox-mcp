import logging
import pytest
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

@pytest.fixture
def test_mcp_with_middleware():
    """Create a temporary MCP instance with middleware for testing."""
    from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
    from fastmcp.server.middleware.logging import LoggingMiddleware

    mcp = FastMCP("TestMiddleware")
    mcp.add_middleware(ErrorHandlingMiddleware())
    mcp.add_middleware(LoggingMiddleware())

    @mcp.tool
    async def ping() -> str:
        return "pong"

    @mcp.tool
    async def fail() -> str:
        raise ValueError("Something went wrong")

    @mcp.tool
    async def fail_tool_error() -> str:
        raise ToolError("Expected tool error")

    return mcp

@pytest.mark.asyncio
async def test_logging_middleware(test_mcp_with_middleware, caplog):
    """Verify that logging middleware logs requests."""
    from fastmcp import Client
    import logging

    # Create a custom logger that propagates to ensure caplog catches it
    custom_logger = logging.getLogger("test_middleware_logger")
    custom_logger.setLevel(logging.INFO)
    
    # Re-add middleware with custom logger
    from fastmcp.server.middleware.logging import LoggingMiddleware
    # Clear existing middleware (if possible, or just append)
    # fastmcp doesn't expose remove_middleware easily, so we just add another one
    test_mcp_with_middleware.add_middleware(LoggingMiddleware(logger=custom_logger))
    
    caplog.set_level(logging.INFO)
    
    async with Client(test_mcp_with_middleware) as client:
        await client.call_tool("ping")
        
    # We look for ANY record from our custom logger
    assert any("tools/call" in r.message or "ping" in r.message for r in caplog.records if r.name == "test_middleware_logger")

@pytest.mark.asyncio
async def test_error_handling_middleware(test_mcp_with_middleware):
    """Verify that error handling middleware catches exceptions."""
    from fastmcp import Client
    from mcp.types import CallToolResult
    
    async with Client(test_mcp_with_middleware) as client:
        # 1. Standard Exception -> Should be caught and returned as ToolError or internal error
        # FastMCP client raises Exception on tool error usually? 
        # Or returns a Result with isError=True?
        
        # In FastMCP client, call_tool returns CallToolResult.
        # If the server returns an error, it might be in content or raise an exception depending on transport/client logic.
        # The in-memory client usually re-raises exceptions if they bubble up, 
        # but ErrorHandlingMiddleware should catch them and return a formatted error response.
        
        try:
            await client.call_tool("fail")
            # If middleware swallows it and returns error result, we check result
            # But ErrorHandlingMiddleware might just format the JSON-RPC error.
        except Exception as e:
            assert "Something went wrong" in str(e)

        # 2. ToolError -> Should be passed through cleanly
        try:
            await client.call_tool("fail_tool_error")
        except Exception as e:
            assert "Expected tool error" in str(e)
