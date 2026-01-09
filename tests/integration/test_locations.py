import re
import uuid

import pytest


def get_id(text):
    if not text:
        return None
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r"ID: ([a-f0-9\-]+)", text)
    if m:
        return m.group(1)
    return None


@pytest.mark.anyio
async def test_location_lifecycle(server_session):
    # 1. List locations (initial)
    res = await server_session.call_tool("list_locations", {})
    assert not getattr(res, "isError", False)

    # 2. Create location
    loc_name = f"Test-Loc-{uuid.uuid4().hex[:6]}"
    res = await server_session.call_tool("create_location", {"name": loc_name, "description": "Test Description"})
    assert not getattr(res, "isError", False)
    loc_id = get_id(res.content[0].text)
    assert loc_id is not None

    # 3. Get location
    res = await server_session.call_tool("get_location", {"id": loc_id})
    assert not getattr(res, "isError", False)
    assert loc_name in res.content[0].text

    # 4. Update location
    new_desc = "Updated Description"
    res = await server_session.call_tool("update_location", {"id": loc_id, "description": new_desc})
    assert not getattr(res, "isError", False)

    # Verify update
    res = await server_session.call_tool("get_location", {"id": loc_id})
    assert new_desc in res.content[0].text

    # 5. Tree
    res = await server_session.call_tool("get_locations_tree", {})
    assert not getattr(res, "isError", False)
    assert loc_name in res.content[0].text

    # 6. Delete location
    res = await server_session.call_tool("delete_location", {"id": loc_id})
    assert not getattr(res, "isError", False)

    # 7. Verify deletion (should fail or not be in list)
    res = await server_session.call_tool("get_location", {"id": loc_id})
    assert getattr(res, "isError", False)
