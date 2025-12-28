import asyncio
import os
import random
import string
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

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
    
    u_pass = "Password123!"
    
    async def setup_user(session, name, email, pw):
        print(f"Registering {name}...")
        await session.call_tool("register_user", {
            "name": name, "email": email, "password": pw
        })
        print(f"Logging in as {name}...")
        await session.call_tool("login_user", {
            "username": email, "password": pw
        })

    # Scenario 1: HOMEBOX_PROTECTED_USERS (Full)
    u_name_1 = f"u1_{random_string()}"
    u_email_1 = f"{u_name_1}@example.com"

    async def test_full_protect(session):
        await setup_user(session, u_name_1, u_email_1, u_pass)
        
        print("Testing Update (Should Fail)...")
        res = await session.call_tool("update_user_self", {"name": "New Name"})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Update blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Update succeeded.")

        print("Testing Delete (Should Fail)...")
        res = await session.call_tool("delete_user_self", {})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Delete blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Delete succeeded.")

    await run_scenario(
        "HOMEBOX_PROTECTED_USERS (Full)",
        {"HOMEBOX_PROTECTED_USERS": f"{u_email_1}"},
        test_full_protect
    )

    # Scenario 2: HOMEBOX_NON_DELETABLE_USERS (Delete Only) + Email Loophole Check
    u_name_2 = f"u2_{random_string()}"
    u_email_2 = f"{u_name_2}@example.com"
    
    async def test_delete_protect(session):
        await setup_user(session, u_name_2, u_email_2, u_pass)

        print("Testing Name Update (Same Email) - Should Succeed...")
        res = await session.call_tool("update_user_self", {
            "name": "UpdatedName",
            "email": u_email_2
        })
        if not getattr(res, "isError", False) and "Updated User" in str(res.content):
             print("PASS: Name update succeeded.")
        else:
             print(f"FAIL: Name update failed: {res.content[0].text if res.content else ''}")

        print("Testing Email Update (New Email) - Should Fail (Loophole Protection)...")
        new_email = f"new_{random_string()}@example.com"
        res = await session.call_tool("update_user_self", {
            "name": "UpdatedName",
            "email": new_email
        })
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Email update blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Email update succeeded (Loophole!).")

        print("Testing Delete (Should Fail)...")
        res = await session.call_tool("delete_user_self", {})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Delete blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Delete succeeded.")

    await run_scenario(
        "HOMEBOX_NON_DELETABLE_USERS (Delete Only)",
        {"HOMEBOX_NON_DELETABLE_USERS": f"{u_email_2}"},
        test_delete_protect
    )

    # Scenario 3: 'all' keyword
    u_name_3 = f"u3_{random_string()}"
    u_email_3 = f"{u_name_3}@example.com"

    async def test_all_protect(session):
        await setup_user(session, u_name_3, u_email_3, u_pass)
        print("Testing Update (Should Fail for 'all')...")
        res = await session.call_tool("update_user_self", {"name": "New"})
        if getattr(res, "isError", False) or "disabled" in str(res.content):
             print(f"PASS: Update blocked: {res.content[0].text if res.content else ''}")
        else:
             print(f"FAIL: Update succeeded.")

    await run_scenario(
        "HOMEBOX_PROTECTED_USERS=all",
        {"HOMEBOX_PROTECTED_USERS": "all"},
        test_all_protect
    )

if __name__ == "__main__":
    asyncio.run(main())
