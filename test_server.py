import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_server():
    # Point to your server
    server_params = StdioServerParameters(
        command=".venv4/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=None # It will load from .env automatically via our client.py
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Server returned {len(tools.tools)} tools.")
            
            # Call a simple tool (get_status)
            print("\nCalling 'get_status'...")
            result = await session.call_tool("get_status", arguments={})
            print(f"Result: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test_server())

