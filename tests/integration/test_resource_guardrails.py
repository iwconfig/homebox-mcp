import json
import re

import pytest
from conftest import random_string, run_scenario_session


def extract_id(text):
    """Utility to extract ID from tool response text."""
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("id")
    except (json.JSONDecodeError, AttributeError):
        pass

    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r"ID: ([a-f0-9\-]+)", text)
    if m:
        return m.group(1)
    return None


def get_id(res):
    if hasattr(res, "content"):
        text = res.content[0].text
    else:
        text = res

    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("id")
    except (json.JSONDecodeError, AttributeError):
        pass

    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r"ID: ([a-f0-9\-]+)", text)
    if m:
        return m.group(1)
    return None


@pytest.mark.anyio
async def test_readonly_resource_type():
    env_vars = {"HOMEBOX_READONLY_RESOURCES": "locations"}
    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("create_location", {"name": "ReadOnlyLoc"}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_non_deletable_resource_type():
    env_vars = {"HOMEBOX_NON_DELETABLE_RESOURCES": "labels"}
    async for session in run_scenario_session(env_vars):
        # Create (Allowed)
        res = await session.call_tool("create_label", {"name": f"Lbl_{random_string()}"}, raise_on_error=False)
        assert not res.is_error
        lbl_id = get_id(res)

        # Update (Allowed)
        res = await session.call_tool("update_label", {"id": lbl_id, "color": "#000000"}, raise_on_error=False)
        assert not res.is_error

        # Delete (Blocked)
        res = await session.call_tool("delete_label", {"id": lbl_id}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_protected_id():
    # Pre-setup: Create Item to get an ID
    item_id = None
    async for session in run_scenario_session({}):
        l_res = await session.call_tool("create_location", {"name": "GuardrailLoc"}, raise_on_error=False)
        l_id = get_id(l_res)
        i_res = await session.call_tool(
            "create_item", {"name": "ProtectedItem", "location_id": l_id}, raise_on_error=False
        )
        item_id = get_id(i_res)

    assert item_id is not None

    env_vars = {"HOMEBOX_PROTECTED_IDS": item_id}
    async for session in run_scenario_session(env_vars):
        # Update (Should Fail)
        res = await session.call_tool("update_item", {"id": item_id, "notes": "Hacked"}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()

        # Delete (Should Fail)
        res = await session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_non_deletable_id():
    # Pre-setup: Create Item
    item_id = None
    async for session in run_scenario_session({}):
        l_res = await session.call_tool("create_location", {"name": "GuardrailLoc2"}, raise_on_error=False)
        l_id = get_id(l_res)
        i_res = await session.call_tool(
            "create_item", {"name": "NonDelItem", "location_id": l_id}, raise_on_error=False
        )
        item_id = get_id(i_res)

    assert item_id is not None

    env_vars = {"HOMEBOX_NON_DELETABLE_IDS": item_id}
    async for session in run_scenario_session(env_vars):
        # Update (Should Succeed)
        res = await session.call_tool("update_item", {"id": item_id, "notes": "SafeUpdate"}, raise_on_error=False)
        assert not res.is_error

        # Delete (Should Fail)
        res = await session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_wipe_inventory_disabled_by_default():
    """Test that wipe_inventory is disabled by default."""
    async for session in run_scenario_session({}):
        res = await session.call_tool("wipe_inventory", {}, raise_on_error=False)
        assert res.is_error
        assert "disabled" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_wipe_inventory_blocked_by_non_deletable():
    """Test that wipe_inventory is blocked by guardrails even if enabled via safety switch."""
    env_vars = {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true", "HOMEBOX_NON_DELETABLE_RESOURCES": "inventory"}

    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("wipe_inventory", {}, raise_on_error=False)
        assert res.is_error
        assert "disabled for resource type 'inventory'" in res.content[0].text


@pytest.mark.anyio
async def test_wipe_inventory_blocked_by_readonly():
    """Test that wipe_inventory is blocked by readonly guardrails even if enabled via safety switch."""
    env_vars = {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true", "HOMEBOX_READONLY_RESOURCES": "inventory"}
    async for session in run_scenario_session(env_vars):
        res = await session.call_tool("wipe_inventory", {}, raise_on_error=False)
        assert res.is_error
        assert "disabled for resource type 'inventory'" in res.content[0].text


@pytest.mark.anyio
async def test_wipe_inventory_full_cycle():
    """
    Test the full wipe cycle using a disposable test user.
    """
    test_email = f"test_{random_string()}@example.com"
    test_pass = "TestPass123!"
    test_name = "Test User"

    env_vars = {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true"}
    async for session in run_scenario_session(env_vars):
        # 1. Register a temporary user
        reg_res = await session.call_tool(
            "register_user",
            {"name": test_name, "email": test_email, "password": test_pass},
            raise_on_error=False,
        )
        if reg_res.is_error:
            msg = reg_res.content[0].text
            if "403" in msg and "disabled" in msg.lower():
                pytest.skip("User registration is disabled on this Homebox instance (403).")
            return

        try:
            # 2. Login as the new user
            await session.call_tool("login_user", {"username": test_email, "password": test_pass}, raise_on_error=False)

            # 3. Create some dummy data
            l_res = await session.call_tool("create_location", {"name": "WipeTestLoc"}, raise_on_error=False)
            l_id = get_id(l_res)
            await session.call_tool("create_item", {"name": "WipeItem", "location_id": l_id}, raise_on_error=False)

            # 4. Wipe Inventory
            wipe_res = await session.call_tool("wipe_inventory", {"wipe_locations": True}, raise_on_error=False)
            if wipe_res.is_error and "404" in wipe_res.content[0].text:
                pytest.skip("wipe-inventory endpoint not supported by this Homebox version.")
            assert not wipe_res.is_error

            # 5. Verify it's gone
            items_res = await session.call_tool("list_items", {}, raise_on_error=False)
            assert '"total": 0' in items_res.content[0].text or '"total":0' in items_res.content[0].text

        finally:
            # 6. Cleanup
            await session.call_tool("delete_user_self", {}, raise_on_error=False)


@pytest.mark.anyio
async def test_wipe_inventory_blocked_for_protected_user():
    """Test that wipe_inventory is blocked if the current user is protected."""
    test_email = f"test_{random_string()}@example.com"
    test_pass = "TestPass123!"
    test_name = "Test User"

    # We mark this specific test user as PROTECTED
    env_vars = {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true", "HOMEBOX_PROTECTED_USERS": test_email}

    async for session in run_scenario_session(env_vars):
        # 1. Register
        await session.call_tool(
            "register_user",
            {"name": test_name, "email": test_email, "password": test_pass},
            raise_on_error=False,
        )
        # 2. Login
        await session.call_tool("login_user", {"username": test_email, "password": test_pass}, raise_on_error=False)

        # 3. Wipe should fail because user is protected
        res = await session.call_tool("wipe_inventory", {}, raise_on_error=False)
        assert res.is_error
        msg = res.content[0].text.lower()
        assert "disabled" in msg and ("user" in msg or "primary" in msg or "protected" in msg)
