import json
import re

import pytest


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
async def test_misc_tools(server_session):
    # Application Status
    res = await server_session.call_tool("get_status", {}, raise_on_error=False)
    assert not res.is_error
    assert "version" in res.content[0].text.lower()

    # Supported Currencies
    res = await server_session.call_tool("list_currencies", {}, raise_on_error=False)
    assert not res.is_error

    # QR Code Generation
    res = await server_session.call_tool("create_qrcode", {"text": "test-mcp"}, raise_on_error=False)
    assert not res.is_error
    assert res.content[0].type == "image"

    # Barcode Search
    res = await server_session.call_tool(
        "search_product_by_barcode", {"barcode": "3017620422003"}, raise_on_error=False
    )
    assert not res.is_error


@pytest.mark.anyio
async def test_label_images_integration(server_session):
    # Label Image Generation
    loc_res = await server_session.call_tool(
        "create_location", {"name": "Img-Loc"}, raise_on_error=False
    )
    loc_id = get_id(loc_res)
    item_res = await server_session.call_tool(
        "create_item", {"name": "Img-Item", "location_id": loc_id}, raise_on_error=False
    )
    item_id = get_id(item_res)

    # Location Label
    res = await server_session.call_tool("get_label_image", {"type": "location", "id": loc_id}, raise_on_error=False)
    assert not res.is_error
    assert res.content[0].type == "image"

    # Item Label
    res = await server_session.call_tool("get_label_image", {"type": "item", "id": item_id}, raise_on_error=False)
    assert not res.is_error
    assert res.content[0].type == "image"

    # Cleanup
    await server_session.call_tool("delete_item", {"id": item_id}, raise_on_error=False)
    await server_session.call_tool("delete_location", {"id": loc_id}, raise_on_error=False)
