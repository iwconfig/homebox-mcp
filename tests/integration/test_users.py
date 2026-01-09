import pytest
import uuid
import random
import string
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

async def run_user_test_session():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Enable safety switches for the lifecycle test
    env["HOMEBOX_ALLOW_USER_REGISTRATION"] = "true"
    env["HOMEBOX_ALLOW_USER_DELETION"] = "true"
    
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
            yield session

@pytest.mark.anyio
async def test_user_lifecycle():
    async for server_session in run_user_test_session():
        # 1. Get Self
        res = await server_session.call_tool("get_user_self", {})
        assert not getattr(res, "isError", False)

        # 2. Register User
        new_name = "Test User"
        new_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        new_pass = "Password123!"
        
        res = await server_session.call_tool("register_user", {
            "name": new_name,
            "email": new_email,
            "password": new_pass
        })
        assert not getattr(res, "isError", False)

        # 3. Login
        res = await server_session.call_tool("login_user", {
            "username": new_email,
            "password": new_pass
        })
        assert not getattr(res, "isError", False)
        assert "Logged in" in res.content[0].text

        # 4. Update Self (while logged in as new user)
        updated_name = "Updated Test User"
        res = await server_session.call_tool("update_user_self", {"name": updated_name})
        assert not getattr(res, "isError", False)
        assert updated_name in res.content[0].text

        # 5. Change Password
        res = await server_session.call_tool("change_password", {
            "current": new_pass,
            "new": "NewPassword123!"
        })
        assert not getattr(res, "isError", False)

        # 6. Delete User Self
        res = await server_session.call_tool("delete_user_self", {})
        assert not getattr(res, "isError", False)

        # 7. Logout (reverts to default user)
        res = await server_session.call_tool("logout_user", {})
        assert not getattr(res, "isError", False)