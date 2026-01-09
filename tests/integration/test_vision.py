import base64
import json
import os
import re

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
    m = re.search(r'ID: ([a-f0-9\-]+)', text)
    if m:
        return m.group(1)
    return None

async def run_vision_session(inbox_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    env["HOMEBOX_INBOX_DIR"] = str(inbox_path)

    server_params = StdioServerParameters(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

@pytest.mark.anyio
async def test_finalize_local_file_lifecycle(tmp_path):
    """
    Test the full lifecycle of finalizing a local file from the inbox.
    Ensures quantity is 1 and mandatory fields are initialized (avoiding 500s).
    """
    # Setup a dummy inbox directory
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    test_file = inbox_dir / "test_item.png"

    # verified 100x100 black PNG
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAANElEQVR4nO3BAQ0AAADCoPdPbQ43oAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAfgx1lAABqFDyOQAAAABJRU5ErkJggg=="
    )
    test_file.write_bytes(png_data)

    async for session in run_vision_session(inbox_dir):
        # We need a location to move the item to
        loc_res = await session.call_tool("create_location", {"name": "Vision-Test-Loc"})
        loc_id = get_id(loc_res)

        try:
            # 1. Check inbox queue
            queue_res = await session.call_tool("get_inbox_queue", {})
            assert "test_item.png" in queue_res.content[0].text

            # 2. Finalize the item
            finalize_res = await session.call_tool("finalize_processed_item", {
                "id": "test_item.png",
                "name": "Finalized Item",
                "location_id": loc_id,
                "source": "local",
                "manufacturer": "Test Corp",
                "notes": "Test Notes"
            })
            assert not getattr(finalize_res, "isError", False)
            item_id = get_id(finalize_res)

            # 3. Verify item details (especially quantity and dates)
            item_details = await session.call_tool("get_item", {"id": item_id})
            data = json.loads(item_details.content[0].text)

            assert data["name"] == "Finalized Item"
            assert data["quantity"] == 1
            assert data["manufacturer"] == "Test Corp"
            # Verify mandatory dates are handled (success means PUT didn't 500)
            assert data.get("purchaseTime") in ["0001-01-01T00:00:00Z", ""]

            # 4. Verify file was cleaned up from inbox
            assert not test_file.exists()

        finally:
            if 'item_id' in locals() and item_id:
                await session.call_tool("delete_item", {"id": item_id})
            await session.call_tool("delete_location", {"id": loc_id})

@pytest.mark.anyio
async def test_split_item_from_image_robustness(tmp_path):
    """
    Test splitting a local file into multiple items.
    Ensures snake_case keys in extracted_objects work and quantity is 1 for each.
    """
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    test_file = inbox_dir / "split_me.png"
    # verified 100x100 black PNG
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAANElEQVR4nO3BAQ0AAADCoPdPbQ43oAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAfgx1lAABqFDyOQAAAABJRU5ErkJggg=="
    )
    test_file.write_bytes(png_data)

    async for session in run_vision_session(inbox_dir):
        loc_res = await session.call_tool("create_location", {"name": "Split-Test-Loc"})
        loc_id = get_id(loc_res)

        try:
            # Split into two items using snake_case keys
            split_res = await session.call_tool("split_item_from_image", {
                "id": "split_me.png",
                "source": "local",
                "extracted_objects": [
                    {
                        "name": "Sub Item 1",
                        "location_id": loc_id,
                        "crop_box": [0, 0, 500, 1000]
                    },
                    {
                        "name": "Sub Item 2",
                        "location_id": loc_id,
                        "crop_box": [500, 0, 1000, 1000]
                    }
                ]
            })

            assert not getattr(split_res, "isError", False)

            # Verify created IDs
            data = json.loads(split_res.content[0].text)
            created_ids = data.get("created_ids", [])
            assert len(created_ids) == 2

            for itm_id in created_ids:
                details = await session.call_tool("get_item", {"id": itm_id})
                itm_data = json.loads(details.content[0].text)
                assert itm_data["quantity"] == 1
                assert itm_data.get("purchaseTime") in ["0001-01-01T00:00:00Z", ""]
                await session.call_tool("delete_item", {"id": itm_id})

        finally:
            await session.call_tool("delete_location", {"id": loc_id})
