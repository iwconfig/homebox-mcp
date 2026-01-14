import os
import random
import string
import uuid

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase, k=length))


async def run_user_test_session():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Enable safety switches for the lifecycle test
    env["HOMEBOX_ALLOW_USER_REGISTRATION"] = "true"
    env["HOMEBOX_ALLOW_USER_DELETION"] = "true"

    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        pytest.skip("No Homebox credentials found in environment")

    transport = StdioTransport(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=env)

    async with Client(transport=transport) as client:
        yield client


@pytest.mark.anyio
async def test_user_lifecycle():
    async for server_session in run_user_test_session():
        # 1. Get Self
        res = await server_session.call_tool("get_user_self", {}, raise_on_error=False)
        assert not res.is_error

        # 2. Register User
        new_name = "Test User"
        new_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        new_pass = "Password123!"

        res = await server_session.call_tool(
            "register_user", {"name": new_name, "email": new_email, "password": new_pass}, raise_on_error=False
        )
        if res.is_error:
            msg = res.content[0].text
            if "403" in msg and "user registration disabled" in msg.lower():
                import warnings

                warnings.warn("User registration is disabled on this Homebox instance; skipping lifecycle test.")
                pytest.skip("User registration is disabled (403).")
            assert not res.is_error

        # 3. Login
        res = await server_session.call_tool(
            "login_user", {"username": new_email, "password": new_pass}, raise_on_error=False
        )
        assert not res.is_error
        assert "Logged in" in res.content[0].text

        # 4. Update Self (while logged in as new user)
        updated_name = "Updated Test User"
        res = await server_session.call_tool("update_user_self", {"name": updated_name}, raise_on_error=False)
        assert not res.is_error
        assert updated_name in res.content[0].text

        # 5. Change Password
        res = await server_session.call_tool(
            "change_password", {"current": new_pass, "new": "NewPassword123!"}, raise_on_error=False
        )
        assert not res.is_error

        # 6. Delete User Self
        res = await server_session.call_tool("delete_user_self", {}, raise_on_error=False)
        assert not res.is_error

        # 7. Logout (reverts to default user)
        res = await server_session.call_tool("logout_user", {}, raise_on_error=False)
        assert not res.is_error
