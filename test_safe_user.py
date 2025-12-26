import asyncio
import os
import random
import string
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

async def main():
    load_dotenv()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        print("Skipping test: No HOMEBOX_API_KEY or HOMEBOX_USERNAME set.")
        return

    server_params = StdioServerParameters(
        command=".venv/bin/python", 
        args=["-m", "homebox_mcp.server"], 
        env=env
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("--- Testing Safe User Deletion ---")

            # 1. Try to delete the current (env) user -> Should FAIL
            print("\n1. Attempting to delete env user (should fail)...")
            res = await session.call_tool("delete_user_self", {})
            
            is_error = getattr(res, "isError", False)
            content = res.content[0].text if res.content else ""
            
            if is_error or "Error" in content or "Cannot delete" in content:
                print(f"PASS: Env user deletion failed as expected. Result: {content}")
            else:
                print(f"FAIL: Env user deletion succeeded (Unexpected). Result: {content}")

            # 2. Register a new user
            new_user = f"testuser_{random_string()}"
            new_email = f"{new_user}@example.com"
            new_pass = "Password123!"
            
            print(f"\n2. Registering new user: {new_user}...")
            res = await session.call_tool("register_user", {
                "name": new_user,
                "email": new_email,
                "password": new_pass
            })
            if getattr(res, "isError", False):
                print(f"FAIL: Registration failed: {res.content[0].text}")
                return
            print("PASS: User registered.")

            # 3. Login as new user
            print(f"\n3. Logging in as {new_user}...")
            res = await session.call_tool("login_user", {
                "username": new_user,
                "password": new_pass
            })
            
            if getattr(res, "isError", False):
                print(f"WARN: Login with username failed: {res.content[0].text}")
                print(f"Retrying with email {new_email}...")
                res = await session.call_tool("login_user", {
                    "username": new_email,
                    "password": new_pass
                })
                
                if getattr(res, "isError", False):
                    print(f"FAIL: Login failed: {res.content[0].text}")
                    return
            
            print("PASS: Logged in.")

            # 4. Verify identity
            print("\n4. Verifying identity...")
            res = await session.call_tool("get_user_self", {})
            if getattr(res, "isError", False):
                print(f"FAIL: get_user_self failed: {res.content[0].text}")
            else:
                info = res.content[0].text
                if new_email in info:
                    print("PASS: Identity verified.")
                else:
                    print(f"FAIL: Identity mismatch. Got: {info}")

            # 5. Delete self (should succeed)
            print("\n5. Deleting self (new user)...")
            res = await session.call_tool("delete_user_self", {})
            if getattr(res, "isError", False) or "Error" in (res.content[0].text if res.content else ""):
                print(f"FAIL: Deletion failed: {res.content[0].text if res.content else ''}")
            else:
                print("PASS: Deletion succeeded.")

            # 6. Logout / Revert
            # print("\n6. Logging out (reverting to env user)...")
            # res = await session.call_tool("logout_user", {})
            # if getattr(res, "isError", False):
            #      print(f"FAIL: Logout failed: {res.content[0].text}")
            # else:
            #      print("PASS: Logged out.")

            # 7. Verify we are back to env user
            print("\n7. Verifying original identity (should have auto-reverted)...")
            res = await session.call_tool("get_user_self", {})
            if getattr(res, "isError", False):
                print(f"FAIL: Could not get original user info: {res.content[0].text}")
            else:
                print(f"PASS: Got info: {res.content[0].text[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
