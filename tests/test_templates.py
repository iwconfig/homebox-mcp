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
    # 1. List templates
    res = await server_session.call_tool("list_templates", {})
    assert not getattr(res, "isError", False)

    # 2. Create template
    t_name = f"Test-Template-{uuid.uuid4().hex[:6]}"
    res = await server_session.call_tool("create_template", {"name": t_name, "description": "Desc"})
    assert not getattr(res, "isError", False)
    t_id = get_id(res.content[0].text)
    assert t_id is not None

    # 3. Get template
    res = await server_session.call_tool("get_template", {"id": t_id})
    assert not getattr(res, "isError", False)
    assert t_name in res.content[0].text

    # 4. Update template
    res = await server_session.call_tool("update_template", {"id": t_id, "description": "Updated Desc"})
    assert not getattr(res, "isError", False)

    # 5. Create item from template
    # Need a location
    loc_res = await server_session.call_tool("create_location", {"name": "Tmpl-Loc"})
    loc_id = get_id(loc_res.content[0].text)
    
    res = await server_session.call_tool("create_item_from_template", {
        "id": t_id,
        "name": "Item-From-Template",
        "locationId": loc_id
    })
    assert not getattr(res, "isError", False)
    item_id = get_id(res.content[0].text)
    assert item_id is not None

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_template", {"id": t_id})
    await server_session.call_tool("delete_location", {"id": loc_id})
