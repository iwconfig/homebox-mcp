import pytest


@pytest.mark.anyio
async def test_actions(server_session):
    # These actions usually return a success message or JSON status

    res = await server_session.call_tool("create_missing_thumbnails", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("ensure_asset_ids", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("ensure_import_refs", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("set_primary_photos", {})
    assert not getattr(res, "isError", False)

    res = await server_session.call_tool("zero_item_time_fields", {})
    assert not getattr(res, "isError", False)
