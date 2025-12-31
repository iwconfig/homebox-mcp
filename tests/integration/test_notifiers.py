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
    # Setup
    n_name = f"Test-Notifier-{uuid.uuid4().hex[:6]}"
    webhook_url = f"generic+{local_http_server}/"

    # Create Notifier
    res = await server_session.call_tool("create_notifier", {
        "name": n_name,
        "url": webhook_url
    })
    assert not getattr(res, "isError", False)
    n_id = get_id(res.content[0].text)

    # Update Notifier
    res = await server_session.call_tool("update_notifier", {"id": n_id, "isActive": False})
    assert not getattr(res, "isError", False)

    # Test Notifier Signal
    res = await server_session.call_tool("test_notifier", {"url": webhook_url})
    assert not getattr(res, "isError", False)

    # List Notifiers
    res = await server_session.call_tool("list_notifiers", {})
    assert not getattr(res, "isError", False)

    # Delete Notifier
    res = await server_session.call_tool("delete_notifier", {"id": n_id})
    assert not getattr(res, "isError", False)