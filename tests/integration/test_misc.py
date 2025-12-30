import pytest
import re

@pytest.mark.anyio
async def test_misc_tools(server_session):
    # 1. Status
    res = await server_session.call_tool("get_status", {})
    assert not getattr(res, "isError", False)
    assert "version" in res.content[0].text.lower()

    # 2. Currency
    res = await server_session.call_tool("list_currencies", {})
    assert not getattr(res, "isError", False)

    # 3. QR Code
    res = await server_session.call_tool("create_qrcode", {"text": "test-mcp"})
    assert not getattr(res, "isError", False)
    assert "QR Code" in res.content[0].text

    # 4. Product Search
    res = await server_session.call_tool("search_product_by_barcode", {"barcode": "0883929085088"})
    assert not getattr(res, "isError", False)

    # 5. Export BOM
    res = await server_session.call_tool("export_bom", {})
    assert not getattr(res, "isError", False)

    # 6. Get Label Image
    # Create a dummy location first to get an ID
    loc_res = await server_session.call_tool("create_location", {"name": "LabelImageLoc"})
    m = re.search(r'"id":\s*"([a-f0-9\-]+)"', loc_res.content[0].text)
    if m:
        loc_id = m.group(1)
        res = await server_session.call_tool("get_label_image", {"type": "location", "id": loc_id})
        assert not getattr(res, "isError", False)
        # Cleanup
        await server_session.call_tool("delete_location", {"id": loc_id})