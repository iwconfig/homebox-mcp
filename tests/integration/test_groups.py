import pytest
import re

@pytest.mark.anyio
async def test_group_tools(server_session):
    # Get Group
    res = await server_session.call_tool("get_group", {})
    assert not getattr(res, "isError", False)

    # Update Group
    res = await server_session.call_tool("update_group", {"name": "Test Group MCP", "currency": "USD"})
    assert not getattr(res, "isError", False)

    # Group Statistics
    res = await server_session.call_tool("get_group_statistics", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("get_label_statistics", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("get_location_statistics", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("get_purchase_price_statistics", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("get_purchase_price_statistics", {"start": "2020-01-01", "end": "2025-12-31"})
    assert not getattr(res, "isError", False)

    # Group Invitation
    res = await server_session.call_tool("create_group_invitation", {"uses": 1})
    assert not getattr(res, "isError", False)
    assert "token" in res.content[0].text.lower()

@pytest.mark.anyio
async def test_export_bom_integration(server_session):
    # Bill of Materials
    res = await server_session.call_tool("export_bom", {})
    assert not getattr(res, "isError", False)