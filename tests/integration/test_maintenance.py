import pytest
import re
import json

def get_id(res):
    if hasattr(res, "content"):
        text = res.content[0].text
    else:
        text = res
        
    if not text: return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data.get("id")
    except:
        pass
        
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    return None

@pytest.mark.anyio
async def test_maintenance_lifecycle(server_session):
    # Setup
    loc_res = await server_session.call_tool("create_location", {"name": "Maint-Loc"})
    loc_id = get_id(loc_res)
    item_res = await server_session.call_tool("create_item", {"name": "Maint-Item", "location_id": loc_id})
    item_id = get_id(item_res)

    # 1. Create maintenance
    res = await server_session.call_tool("create_item_maintenance", {
        "id": item_id,
        "name": "Periodic Check",
        "cost": 50.0
    })
    assert not getattr(res, "isError", False)
    
    m_id = get_id(res)
    if m_id:
        # 2. Get item maintenance
        res = await server_session.call_tool("get_item_maintenance", {"id": item_id})
        assert not getattr(res, "isError", False)
        assert "Periodic Check" in res.content[0].text

        # 3. Update maintenance entry
        res = await server_session.call_tool("update_maintenance_entry", {
            "id": m_id,
            "name": "Updated Check",
            "cost": 75.0
        })
        assert not getattr(res, "isError", False)
        assert "Updated Check" in res.content[0].text

        # 4. Query all maintenance
        res = await server_session.call_tool("query_all_maintenance", {})
        assert not getattr(res, "isError", False)

        # 5. Delete maintenance entry
        res = await server_session.call_tool("delete_maintenance_entry", {"id": m_id})
        assert not getattr(res, "isError", False)

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id})
    await server_session.call_tool("delete_location", {"id": loc_id})
