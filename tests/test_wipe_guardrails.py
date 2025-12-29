import pytest
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolRequestParams

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_wipe_inventory_blocked_readonly():
    """Test that wipe_inventory is blocked by HOMEBOX_READONLY_RESOURCES."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["HOMEBOX_READONLY_RESOURCES"] = "inventory" # Block inventory modification
    
    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        pytest.skip("No Homebox credentials found in environment")

    server_params = StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Expect failure result
            result = await session.call_tool("wipe_inventory", {})
            
            # Check if result indicates error
            assert result.isError is True
            # The content should contain the error message
            error_text = result.content[0].text
            assert "Action 'delete' is disabled for resource type 'inventory'" in error_text

@pytest.mark.anyio
async def test_wipe_inventory_blocked_non_deletable():
    """Test that wipe_inventory is blocked by HOMEBOX_NON_DELETABLE_RESOURCES."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["HOMEBOX_NON_DELETABLE_RESOURCES"] = "inventory" # Block inventory deletion
    
    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        pytest.skip("No Homebox credentials found in environment")

    server_params = StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Expect failure result
            result = await session.call_tool("wipe_inventory", {})
            
            assert result.isError is True
            error_text = result.content[0].text
            assert "Action 'delete' is disabled for resource type 'inventory'" in error_text

