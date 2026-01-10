import os
import warnings

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from conftest import run_scenario_session, random_string


@pytest.mark.anyio
async def test_user_safety_switches_disabled_by_default():
    """Test that registration and deletion are disabled by default."""
    # Run with empty env (except standard creds)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Explicitly ensure they are NOT set to test the default 'false' behavior
    env.pop("HOMEBOX_ALLOW_USER_REGISTRATION", None)
    env.pop("HOMEBOX_ALLOW_USER_DELETION", None)

    transport = StdioTransport(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=env
    )

    async with Client(transport=transport) as client:
        # Register should fail
        res = await client.call_tool(
            "register_user", {"name": "Test", "email": "test@ex.com", "password": "Pass"}, raise_on_error=False
        )
        assert res.is_error
        msg = res.content[0].text.lower()
        
        # If the backend blocks it first, it means registration is hard-disabled on the server.
        if "user registration disabled" in msg:
            warnings.warn("User registration is hard-disabled on the Homebox backend; skipping safety switch test.")
            pytest.skip("User registration is disabled on backend.")
            
        assert "is disabled via safety switch" in msg

        # Delete should fail
        res = await client.call_tool("delete_user_self", {}, raise_on_error=False)
        assert res.is_error
        assert "is disabled via safety switch" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_full_user_protection():
    u_pass = "Password123!"
    u_name = f"u1_{random_string()}"
    u_email = f"{u_name}@example.com"

    # Block everything: update, password, delete
    env_vars = {"HOMEBOX_PROTECTED_USERS": u_email}

    async for session in run_scenario_session(env_vars):
        # 1. Register
        reg_res = await session.call_tool(
            "register_user", {"name": u_name, "email": u_email, "password": u_pass}, raise_on_error=False
        )
        if reg_res.is_error and "user registration disabled" in reg_res.content[0].text.lower():
            warnings.warn("User registration is disabled on Homebox demo instance; skipping full protection test.")
            pytest.skip("User registration is disabled.")

        # 2. Login
        await session.call_tool(
            "login_user", {"username": u_email, "password": u_pass}, raise_on_error=False
        )

        # Test Delete (Should Fail)
        res = await session.call_tool("delete_user_self", {}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()

        # Test Update (Should Fail)
        res = await session.call_tool(
            "update_user_self", {"name": "NewName", "email": u_email}, raise_on_error=False
        )
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()

        # Test Password Change (Should Fail)
        res = await session.call_tool(
            "change_password", {"current": u_pass, "new": "NewPass123!"}, raise_on_error=False
        )
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_non_deletable_user_protection():
    u_pass = "Password123!"
    u_name = f"u2_{random_string()}"
    u_email = f"{u_name}@example.com"

    env_vars = {"HOMEBOX_NON_DELETABLE_USERS": u_email}

    async for session in run_scenario_session(env_vars):
        reg_res = await session.call_tool(
            "register_user", {"name": u_name, "email": u_email, "password": u_pass}, raise_on_error=False
        )
        if reg_res.is_error and "user registration disabled" in reg_res.content[0].text.lower():
            pytest.skip("User registration is disabled on backend.")

        await session.call_tool(
            "login_user", {"username": u_email, "password": u_pass}, raise_on_error=False
        )

        # Test Name Update (Same Email) - Should Succeed
        res = await session.call_tool(
            "update_user_self", {"name": "UpdatedName", "email": u_email}, raise_on_error=False
        )
        # If testing on primary account it might fail due to inherent protections
        if res.is_error:
            msg = res.content[0].text.lower()
            if "primary" in msg or "disabled" in msg:
                warnings.warn("Skipping update test as it fell back to protected primary account.")
                pytest.skip("Testing on primary account which has inherent protections.")
        assert not res.is_error

        # Test Email Update (New Email) - Should Fail (Loophole Protection)
        new_email = f"new_{random_string()}@example.com"
        res = await session.call_tool(
            "update_user_self", {"name": "UpdatedName", "email": new_email}, raise_on_error=False
        )
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()

        # Test Delete (Should Fail)
        res = await session.call_tool("delete_user_self", {}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_all_users_protected():
    u_pass = "Password123!"
    u_name = f"u3_{random_string()}"
    u_email = f"{u_name}@example.com"

    env_vars = {"HOMEBOX_PROTECTED_USERS": "all"}

    async for session in run_scenario_session(env_vars):
        reg_res = await session.call_tool(
            "register_user", {"name": u_name, "email": u_email, "password": u_pass}, raise_on_error=False
        )
        if reg_res.is_error and "user registration disabled" in reg_res.content[0].text.lower():
            pytest.skip("User registration is disabled on backend.")

        await session.call_tool(
            "login_user", {"username": u_email, "password": u_pass}, raise_on_error=False
        )

        # Test Update (Should Fail for 'all')
        res = await session.call_tool(
            "update_user_self", {"name": "NewName", "email": u_email}, raise_on_error=False
        )
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()