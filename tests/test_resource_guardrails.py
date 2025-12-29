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
    env.update(env_vars)

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