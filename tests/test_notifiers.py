import pytest
import re
import uuid

def get_id(text):
    if not text: return None
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    return None

@pytest.mark.anyio
async def test_notifier_lifecycle(server_session, local_http_server):
    # 1. List notifiers
    res = await server_session.call_tool("list_notifiers", {})
    assert not getattr(res, "isError", False)

    # 2. Create notifier
    n_name = f"Test-Notifier-{uuid.uuid4().hex[:6]}"

    # Use generic+http scheme for Shoutrrr to hit our local server
    webhook_url = f"generic+{local_http_server}/"
    res = await server_session.call_tool("create_notifier", {
        "name": n_name,
        "url": webhook_url
    })

    assert not getattr(res, "isError", False)
    n_id = get_id(res.content[0].text)
    assert n_id is not None

    # 3. Update notifier
    res = await server_session.call_tool("update_notifier", {"id": n_id, "isActive": False})
    assert not getattr(res, "isError", False)

    # 4. Test notifier
    res = await server_session.call_tool("test_notifier", {"url": webhook_url})
    assert not getattr(res, "isError", False)


    # This might fail if the URL is invalid, but we check if the tool executes
    assert not getattr(res, "isError", False)

    # 5. Delete notifier
    res = await server_session.call_tool("delete_notifier", {"id": n_id})
    assert not getattr(res, "isError", False)
