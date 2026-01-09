import pytest


@pytest.mark.anyio
async def test_actions(server_session):
    # These actions usually return a success message or JSON status

    res = await server_session.call_tool("create_missing_thumbnails", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("ensure_asset_ids", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("ensure_import_refs", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("set_primary_photos", {}, raise_on_error=False)
    assert not res.is_error

    res = await server_session.call_tool("zero_item_time_fields", {}, raise_on_error=False)
    assert not res.is_error
