import pytest


@pytest.mark.anyio
async def test_group_tools(server_session):
    # Get Group
    res = await server_session.call_tool("get_group", {}, raise_on_error=False)
    assert not res.is_error

    # Update Group
    res = await server_session.call_tool(
        "update_group", {"name": "Test Group MCP", "currency": "USD"}, raise_on_error=False
    )
    assert not res.is_error

    # Group Statistics
    res = await server_session.call_tool("get_group_statistics", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("get_label_statistics", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("get_location_statistics", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("get_purchase_price_statistics", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool(
        "get_purchase_price_statistics", {"start": "2020-01-01", "end": "2025-12-31"}, raise_on_error=False
    )
    assert not res.is_error

    # Group Invitation
    res = await server_session.call_tool("create_group_invitation", {"uses": 1}, raise_on_error=False)
    assert not res.is_error
    assert "token" in res.content[0].text.lower()


@pytest.mark.anyio
async def test_export_bom_integration(server_session):
    # Bill of Materials
    res = await server_session.call_tool("export_bom", {}, raise_on_error=False)
    assert not res.is_error
