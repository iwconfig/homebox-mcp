import pytest
import re
import uuid

def get_id(text):
    if not text: return None
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    return None

@pytest.mark.anyio
async def test_template_lifecycle(server_session):
    # Setup
    t_name = f"Test-Template-{uuid.uuid4().hex[:6]}"
    loc_res = await server_session.call_tool("create_location", {"name": "Tmpl-Loc"})
    loc_id = get_id(loc_res.content[0].text)

    # Create Template
    res = await server_session.call_tool("create_template", {"name": t_name, "description": "Desc"})
    assert not getattr(res, "isError", False)
    t_id = get_id(res.content[0].text)

    # Get Template
    res = await server_session.call_tool("get_template", {"id": t_id})
    assert not getattr(res, "isError", False)

    # Update Template
    res = await server_session.call_tool("update_template", {"id": t_id, "description": "Updated"})
    assert not getattr(res, "isError", False)

    # Create Item from Template
    res = await server_session.call_tool("create_item_from_template", {
        "id": t_id,
        "name": "Item-From-Template",
        "locationId": loc_id
    })
    assert not getattr(res, "isError", False)
    item_id = get_id(res.content[0].text)

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_template", {"id": t_id})
    await server_session.call_tool("delete_location", {"id": loc_id})