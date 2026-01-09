import os
import random
import string

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase, k=length))


async def run_scenario_session(env_vars):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Enable safety switches for guardrail tests
    env["HOMEBOX_ALLOW_USER_REGISTRATION"] = "true"
    env["HOMEBOX_ALLOW_USER_DELETION"] = "true"
    env.update(env_vars)

    server_params = StdioServerParameters(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=env)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.anyio
async def test_user_safety_switches_disabled_by_default():
    """Test that registration and deletion are disabled by default."""
    # Run with empty env (except standard creds)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Explicitly ensure they are NOT set
    env.pop("HOMEBOX_ALLOW_USER_REGISTRATION", None)
    env.pop("HOMEBOX_ALLOW_USER_DELETION", None)

    server_params = StdioServerParameters(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=env)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Register should fail
            res = await session.call_tool("register_user", {"name": "Test", "email": "test@ex.com", "password": "Pass"})
            assert res.isError is True
            assert "is disabled via safety switch" in res.content[0].text

            # Delete should fail
            res = await session.call_tool("delete_user_self", {})
            assert res.isError is True
            assert "is disabled via safety switch" in res.content[0].text


@pytest.mark.anyio
async def test_full_user_protection():
    u_pass = "Password123!"
    u_name = f"u1_{random_string()}"
    u_email = f"{u_name}@example.com"

    env_vars = {"HOMEBOX_PROTECTED_USERS": u_email}

    async for session in run_scenario_session(env_vars):
        # Setup: Register and Login
        await session.call_tool("register_user", {"name": u_name, "email": u_email, "password": u_pass})
        await session.call_tool("login_user", {"username": u_email, "password": u_pass})

        # Test Update (Should Fail)
        res = await session.call_tool("update_user_self", {"name": "New Name"})
        assert res.isError is True
        assert "disabled" in res.content[0].text.lower()

        # Test Delete (Should Fail)
        res = await session.call_tool("delete_user_self", {})
        assert res.isError is True
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_non_deletable_user_protection():
    u_pass = "Password123!"
    u_name = f"u2_{random_string()}"
    u_email = f"{u_name}@example.com"

    env_vars = {"HOMEBOX_NON_DELETABLE_USERS": u_email}

    async for session in run_scenario_session(env_vars):
        # Setup
        await session.call_tool("register_user", {"name": u_name, "email": u_email, "password": u_pass})
        await session.call_tool("login_user", {"username": u_email, "password": u_pass})

        # Test Name Update (Same Email) - Should Succeed
        res = await session.call_tool("update_user_self", {"name": "UpdatedName", "email": u_email})
        assert not getattr(res, "isError", False)

        # Test Email Update (New Email) - Should Fail (Loophole Protection)
        new_email = f"new_{random_string()}@example.com"
        res = await session.call_tool("update_user_self", {"name": "UpdatedName", "email": new_email})
        assert res.isError is True
        assert "disabled" in res.content[0].text.lower()

        # Test Delete (Should Fail)
        res = await session.call_tool("delete_user_self", {})
        assert res.isError is True
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_all_users_protected():
    u_pass = "Password123!"
    u_name = f"u3_{random_string()}"
    u_email = f"{u_name}@example.com"

    env_vars = {"HOMEBOX_PROTECTED_USERS": "all"}

    async for session in run_scenario_session(env_vars):
        # Setup
        await session.call_tool("register_user", {"name": u_name, "email": u_email, "password": u_pass})
        await session.call_tool("login_user", {"username": u_email, "password": u_pass})

        # Test Update (Should Fail for 'all')
        res = await session.call_tool("update_user_self", {"name": "New"})
        assert res.isError is True
        assert "disabled" in res.content[0].text.lower()
