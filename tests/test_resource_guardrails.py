import asyncio
import os
import re
import random
import string
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def get_id(text):
    if not text: return None
    # Flexible ID extraction
    m = re.search(r'"id": "([a-f0-9\-]+)"', text)
    if m: return m.group(1)
    m = re.search(r'ID: ([a-f0-9\-]+)', text)
    if m: return m.group(1)
    return None

async def run_scenario(name, env_vars, actions):
    print(f"\n=== SCENARIO: {name} ===")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env.update(env_vars)

    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
         print("Skipping: No credentials.")
         return

    server_params = StdioServerParameters(
        command=".venv/bin/python", 
        args=["-m", "homebox_mcp.server"], 
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await actions(session)

async def main():
    load_dotenv() 
    
    # 1. Test Read-Only Resource Type (Locations)
    async def test_readonly_type(session):
        print("Testing Create Location (Should Fail)...")
        res = await session.call_tool("create_location", {"name": "ReadOnlyLoc"})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Create blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Create succeeded: {res.content[0].text if res.content else ''}")

    await run_scenario(
        "HOMEBOX_READONLY_RESOURCES=locations",
        {"HOMEBOX_READONLY_RESOURCES": "locations"},
        test_readonly_type
    )

    # 2. Test Non-Deletable Resource Type (Labels)
    async def test_non_deletable_type(session):
        # Create (Allowed)
        print("Creating Label...")
        res = await session.call_tool("create_label", {"name": f"Lbl_{random_string()}"})
        lbl_id = get_id(res.content[0].text)
        
        # Update (Allowed)
        print("Updating Label (Should Succeed)...")
        res = await session.call_tool("update_label", {"id": lbl_id, "color": "#000"})
        if not getattr(res, "isError", False):
             print("PASS: Update succeeded.")
        else:
             print(f"FAIL: Update blocked: {res.content[0].text}")

        # Delete (Blocked)
        print("Deleting Label (Should Fail)...")
        res = await session.call_tool("delete_label", {"id": lbl_id})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Delete blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Delete succeeded.")

    await run_scenario(
        "HOMEBOX_NON_DELETABLE_RESOURCES=labels",
        {"HOMEBOX_NON_DELETABLE_RESOURCES": "labels"},
        test_non_deletable_type
    )

    # 3. Test Protected ID (Item)
    # We need an ID first. I'll create one in a setup phase (normal run), then pass it.
    # Actually, I can create it inside the scenario if I don't protect Create.
    # But I want to protect ID. I can't protect an ID before I know it.
    # So I have to create it, get ID, then run scenario with that ID in env. 
    
    # Pre-step: Create Item
    print("\n--- Setup: Creating Item for ID tests ---")
    setup_env = os.environ.copy()
    setup_env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    server_params = StdioServerParameters(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=setup_env)
    
    item_id = None
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Need a location first
            l_res = await session.call_tool("create_location", {"name": "GuardrailLoc"})
            l_id = get_id(l_res.content[0].text)
            
            i_res = await session.call_tool("create_item", {"name": "ProtectedItem", "locationId": l_id})
            item_id = get_id(i_res.content[0].text)
            print(f"Created Item ID: {item_id}")

    if item_id:
        async def test_protected_id(session):
            print("Updating Item (Should Fail)...")
            res = await session.call_tool("update_item", {"id": item_id, "notes": "Hacked"})
            if getattr(res, "isError", False) or "disabled" in str(res.content):
                print(f"PASS: Update blocked: {res.content[0].text if res.content else ''}")
            else:
                print(f"FAIL: Update succeeded.")

            print("Deleting Item (Should Fail)...")
            res = await session.call_tool("delete_item", {"id": item_id})
            if getattr(res, "isError", False) or "disabled" in str(res.content):
                print(f"PASS: Delete blocked: {res.content[0].text if res.content else ''}")
            else:
                print(f"FAIL: Delete succeeded.")

        await run_scenario(
            "HOMEBOX_PROTECTED_IDS=<item_id>",
            {"HOMEBOX_PROTECTED_IDS": item_id},
            test_protected_id
        )

    # 4. Test Non-Deletable ID (Item)
    # Reuse location, create new item
    item_id_2 = None
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            i_res = await session.call_tool("create_item", {"name": "NonDelItem", "locationId": l_id})
            item_id_2 = get_id(i_res.content[0].text)
            print(f"Created Item 2 ID: {item_id_2}")

    if item_id_2:
        async def test_non_deletable_id(session):
            print("Updating Item (Should Succeed)...")
            res = await session.call_tool("update_item", {"id": item_id_2, "notes": "SafeUpdate"})
            if not getattr(res, "isError", False):
                print("PASS: Update succeeded.")
            else:
                print(f"FAIL: Update blocked: {res.content[0].text}")

            print("Deleting Item (Should Fail)...")
            res = await session.call_tool("delete_item", {"id": item_id_2})
            if getattr(res, "isError", False) or "disabled" in str(res.content):
                print(f"PASS: Delete blocked: {res.content[0].text if res.content else ''}")
            else:
                print(f"FAIL: Delete succeeded.")

        await run_scenario(
            "HOMEBOX_NON_DELETABLE_IDS=<item_id_2>",
            {"HOMEBOX_NON_DELETABLE_IDS": item_id_2},
            test_non_deletable_id
        )

    # 5. Test Read-Only Users (Registration blocked)
    async def test_readonly_users(session):
        print("Testing Register User (Should Fail)...")
        res = await session.call_tool("register_user", {
            "name": "ShouldFail",
            "email": f"fail_{random_string()}@example.com",
            "password": "Password123!"
        })
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Registration blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Registration succeeded.")

    await run_scenario(
        "HOMEBOX_READONLY_RESOURCES=users",
        {"HOMEBOX_READONLY_RESOURCES": "users"},
        test_readonly_users
    )

if __name__ == "__main__":
    asyncio.run(main())
