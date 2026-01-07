import pytest
import os
import re
import random
import string
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def get_id(text):
    if not text: return None
    m = re.search(r'"id": "([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    m = re.search(r'ID: ([a-f0-9\-]+)', text)
    if m: return m.group(1)
    return None

async def run_scenario_session(env_vars):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Enable safety switches for test setup/cleanup
    env["HOMEBOX_ALLOW_USER_REGISTRATION"] = "true"
    env["HOMEBOX_ALLOW_USER_DELETION"] = "true"
    env.update(env_vars)

    server_params = StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server", "stdio"],
        env=env
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Safety Check: Ensure we aren't using a protected account for tests
            # (Optional: skip if you really want to run against main)
            res = await session.call_tool("get_user_self", {})
            if not getattr(res, "isError", False):
                user_text = res.content[0].text
                # Try to find email
                m = re.search(r'"email": "([^"]+)"', user_text)
                if m:
                    email = m.group(1)
                    # If this email is specifically listed as protected, maybe we should be careful.
                    # For now, we just log it or the user can decide.
                    pass

            yield session


@pytest.mark.anyio
async def test_readonly_resource_type():
    env_vars = {"HOMEBOX_READONLY_RESOURCES": "locations"}
    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("create_location", {"name": "ReadOnlyLoc"})
        assert getattr(res, "isError", False) or "disabled" in str(res.content).lower()

@pytest.mark.anyio
async def test_non_deletable_resource_type():
    env_vars = {"HOMEBOX_NON_DELETABLE_RESOURCES": "labels"}
    async for session in run_scenario_session(env_vars):
        # Create (Allowed)
        res = await session.call_tool("create_label", {"name": f"Lbl_{random_string()}"})
        assert not getattr(res, "isError", False)
        lbl_id = get_id(res.content[0].text)
        
        # Update (Allowed)
        res = await session.call_tool("update_label", {"id": lbl_id, "color": "#000"})
        assert not getattr(res, "isError", False)

        # Delete (Blocked)
        res = await session.call_tool("delete_label", {"id": lbl_id})
        assert getattr(res, "isError", False) or "disabled" in str(res.content).lower()

@pytest.mark.anyio
async def test_protected_id():
    # Pre-setup: Create Item to get an ID
    item_id = None
    async for session in run_scenario_session({}):
        l_res = await session.call_tool("create_location", {"name": "GuardrailLoc"})
        l_id = get_id(l_res.content[0].text)
        i_res = await session.call_tool("create_item", {"name": "ProtectedItem", "locationId": l_id})
        item_id = get_id(i_res.content[0].text)

    assert item_id is not None

    env_vars = {"HOMEBOX_PROTECTED_IDS": item_id}
    async for session in run_scenario_session(env_vars):
        # Update (Should Fail)
        res = await session.call_tool("update_item", {"id": item_id, "notes": "Hacked"})
        assert getattr(res, "isError", False) or "disabled" in str(res.content).lower()

        # Delete (Should Fail)
        res = await session.call_tool("delete_item", {"id": item_id})
        assert getattr(res, "isError", False) or "disabled" in str(res.content).lower()

@pytest.mark.anyio
async def test_non_deletable_id():
    # Pre-setup: Create Item
    item_id = None
    async for session in run_scenario_session({}):
        l_res = await session.call_tool("create_location", {"name": "GuardrailLoc2"})
        l_id = get_id(l_res.content[0].text)
        i_res = await session.call_tool("create_item", {"name": "NonDelItem", "locationId": l_id})
        item_id = get_id(i_res.content[0].text)

    assert item_id is not None

    env_vars = {"HOMEBOX_NON_DELETABLE_IDS": item_id}
    async for session in run_scenario_session(env_vars):
        # Update (Should Succeed)
        res = await session.call_tool("update_item", {"id": item_id, "notes": "SafeUpdate"})
        assert not getattr(res, "isError", False)

        # Delete (Should Fail)
        res = await session.call_tool("delete_item", {"id": item_id})
        assert getattr(res, "isError", False) or "disabled" in str(res.content).lower()

@pytest.mark.anyio
async def test_wipe_inventory_disabled_by_default():
    """Test that wipe_inventory is disabled by default."""
    async for session in run_scenario_session({}):
        res = await session.call_tool("wipe_inventory", {})
        assert res.isError is True
        assert "Safety Lock" in res.content[0].text

@pytest.mark.anyio
async def test_wipe_inventory_blocked_by_non_deletable():
    """Test that wipe_inventory is blocked by guardrails even if enabled via safety switch."""
    env_vars = {
        "HOMEBOX_ALLOW_WIPE_INVENTORY": "true",
        "HOMEBOX_NON_DELETABLE_RESOURCES": "inventory"
    }

    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("wipe_inventory", {})
        assert res.isError is True
        assert "disabled for resource type 'inventory'" in res.content[0].text

@pytest.mark.anyio
async def test_wipe_inventory_blocked_by_readonly():
    """Test that wipe_inventory is blocked by readonly guardrails even if enabled via safety switch."""
    env_vars = {
        "HOMEBOX_ALLOW_WIPE_INVENTORY": "true",
        "HOMEBOX_READONLY_RESOURCES": "inventory"
    }
    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("wipe_inventory", {})
        assert res.isError is True
        assert "disabled for resource type 'inventory'" in res.content[0].text

@pytest.mark.anyio
async def test_wipe_inventory_full_cycle():
    """
    Test the full wipe cycle using a disposable test user.
    This ensures we don't accidentally wipe real data.
    """
    test_email = f"test_{random_string()}@example.com"
    test_pass = "TestPass123!"
    test_name = "Test User"
    
    env_vars = {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true"}
    async for session in run_scenario_session(env_vars):
        # 1. Register a temporary user
        reg_res = await session.call_tool("register_user", {
            "name": test_name, 
            "email": test_email, 
            "password": test_pass
        })
        if getattr(reg_res, "isError", False):
            # If registration fails (e.g. already disabled), skip
            if "disabled" in str(reg_res.content).lower() or "403" in str(reg_res.content):
                pytest.skip("User registration is disabled on this Homebox instance.")
            return

        try:
            # 2. Login as the new user
            await session.call_tool("login_user", {"username": test_email, "password": test_pass})
            
            # 3. Create some dummy data
            l_res = await session.call_tool("create_location", {"name": "WipeTestLoc"})
            l_id = get_id(l_res.content[0].text)
            await session.call_tool("create_item", {"name": "WipeItem", "locationId": l_id})
            
            # 4. Wipe Inventory
            wipe_res = await session.call_tool("wipe_inventory", {"wipeLocations": True})
            if getattr(wipe_res, "isError", False) and "404" in wipe_res.content[0].text:
                pytest.skip("wipe-inventory endpoint not supported by this Homebox version.")
            assert not getattr(wipe_res, "isError", False)
            
            # 5. Verify it's gone
            items_res = await session.call_tool("list_items", {})
            # FastMCP might return raw JSON string in text
            assert '"total": 0' in items_res.content[0].text or '"total":0' in items_res.content[0].text
            
        finally:
            # 6. Cleanup: Re-login if necessary and delete the test user
            # We are already logged in as them
            await session.call_tool("delete_user_self", {})

@pytest.mark.anyio
async def test_wipe_inventory_blocked_for_protected_user():
    """Test that wipe_inventory is blocked if the current user is protected."""
    test_email = f"test_{random_string()}@example.com"
    test_pass = "TestPass123!"
    test_name = "Test User"
    
    # We mark this specific test user as PROTECTED
    env_vars = {
        "HOMEBOX_ALLOW_WIPE_INVENTORY": "true",
        "HOMEBOX_PROTECTED_USERS": test_email
    }
    
    async for session in run_scenario_session(env_vars):
        # 1. Register
        await session.call_tool("register_user", {"name": test_name, "email": test_email, "password": test_pass})
        # 2. Login
        await session.call_tool("login_user", {"username": test_email, "password": test_pass})
        
        # 3. Wipe should fail because user is protected
        res = await session.call_tool("wipe_inventory", {})
        assert res.isError is True
        assert "disabled for protected user" in res.content[0].text or "disabled for user" in res.content[0].text

        # Cleanup: we have to un-protect to delete if we wanted to, 
        # but here we just let it be or the session ends.