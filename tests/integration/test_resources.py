import json
import pytest

@pytest.mark.anyio
async def test_resources_lifecycle(server_session):
    # 1. Create a location
    loc_name = "ResourceLoc"
    loc_res = await server_session.call_tool("create_location", {"name": loc_name})
    loc_data = json.loads(loc_res.content[0].text)
    loc_id = loc_data["id"]

    # 2. Create an item
    item_name = "ResourceItem"
    item_res = await server_session.call_tool("create_item", {"name": item_name, "location_id": loc_id})
    item_data = json.loads(item_res.content[0].text)
    item_id = item_data["id"]
    
    # Re-fetch item to ensure we have the asset ID (sometimes not in create response)
    get_res = await server_session.call_tool("get_item", {"id": item_id})
    full_item_data = json.loads(get_res.content[0].text)
    asset_id = full_item_data.get("assetId")

    try:
        # 3. Test homebox://locations/{id}
        res = await server_session.read_resource(f"homebox://locations/{loc_id}")
        assert res
        content = res[0]
        assert str(content.uri) == f"homebox://locations/{loc_id}"
        data = json.loads(content.text)
        assert data["id"] == loc_id
        assert data["name"] == loc_name

        # 4. Test homebox://items/{id}
        res = await server_session.read_resource(f"homebox://items/{item_id}")
        data = json.loads(res[0].text)
        assert data["id"] == item_id
        assert data["name"] == item_name

        # 5. Test homebox://assets/{id}
        if asset_id:
            # Test raw asset ID
            res = await server_session.read_resource(f"homebox://assets/{asset_id}")
            data = json.loads(res[0].text)
            assert data["id"] == item_id
            
        # 6. Test homebox://status
        res = await server_session.read_resource("homebox://status")
        data = json.loads(res[0].text)
        assert "health" in data

        # 7. Test homebox://locations/tree
        res = await server_session.read_resource("homebox://locations/tree")
        data = json.loads(res[0].text)
        assert isinstance(data, list)
        
        # 8. Test homebox://maintenance
        res = await server_session.read_resource("homebox://maintenance")
        data = json.loads(res[0].text)
        assert isinstance(data, list)

        # 9. Test homebox://labels
        res = await server_session.read_resource("homebox://labels")
        data = json.loads(res[0].text)
        assert isinstance(data, list)
        
        # 10. Test homebox://users/self
        res = await server_session.read_resource("homebox://users/self")
        data = json.loads(res[0].text)
        assert "email" in data["item"] # User response is wrapped

    finally:
        # Clean up
        await server_session.call_tool("delete_item", {"id": item_id})
        await server_session.call_tool("delete_location", {"id": loc_id})
