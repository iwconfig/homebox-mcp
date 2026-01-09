import re
import uuid

import pytest


def get_id(text):
    if not text:
        return None
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', text)
    if m:
        return m.group(1)
    return None


@pytest.mark.anyio
async def test_label_lifecycle(server_session):
    # 1. List labels
    res = await server_session.call_tool("list_labels", {}, raise_on_error=False)
    assert not res.is_error

    # 2. Create label
    lbl_name = f"Test-Lbl-{uuid.uuid4().hex[:6]}"
    res = await server_session.call_tool("create_label", {"name": lbl_name, "color": "#ff0000"}, raise_on_error=False)
    assert not res.is_error
    lbl_id = get_id(res.content[0].text)
    assert lbl_id is not None

    # 3. Get label
    res = await server_session.call_tool("get_label", {"id": lbl_id}, raise_on_error=False)
    assert not res.is_error
    assert lbl_name in res.content[0].text

    # 4. Update label
    res = await server_session.call_tool("update_label", {"id": lbl_id, "color": "#00ff00"}, raise_on_error=False)
    assert not res.is_error

    # 5. Delete label
    res = await server_session.call_tool("delete_label", {"id": lbl_id}, raise_on_error=False)
    assert not res.is_error
