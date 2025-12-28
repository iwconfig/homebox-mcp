import json
import os
import re
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

# Cache to remember IDs that matched protected emails during this process lifecycle
_PROTECTED_ID_CACHE = set()
_NON_DELETABLE_ID_CACHE = set()

def _parse_user_list(env_val: str) -> set[str]:
    """Parses a string containing emails or IDs (comma/space separated) into a set."""
    if not env_val:
        return set()
    # Split by comma or whitespace
    parts = re.split(r'[,\s]+', env_val)
    return {p.strip() for p in parts if p.strip()}

def _check_protection(user_data: dict, env_var: str, action_desc: str):
    """Checks if the user is protected by the given environment variable or cache."""
    val = os.getenv(env_var, "")
    
    # Select the correct cache
    is_non_deletable = "NON_DELETABLE" in env_var
    cache = _NON_DELETABLE_ID_CACHE if is_non_deletable else _PROTECTED_ID_CACHE

    u_id = user_data.get("id")
    u_email = user_data.get("email")
    
    print(f"DEBUG Protection Check: Action={action_desc}, Env={env_var}, User={u_email} ({u_id})")

    # 1. Check Cache first (Immutable ID protection)
    if u_id and u_id in cache:
        raise ValueError(f"Action '{action_desc}' is disabled for protected user ID '{u_id}' (matched via {env_var} previously).")

    if not val:
        return

    protected_set = _parse_user_list(val)
    print(f"DEBUG Protected Set: {protected_set}")
    
    # 2. Check for "all" (case-insensitive)
    if "all" in {s.lower() for s in protected_set}:
        if u_id: cache.add(u_id) # Lock it in
        raise ValueError(f"Action '{action_desc}' is disabled for ALL users via {env_var}.")

    # 3. Check ID Match
    if u_id and u_id in protected_set:
        cache.add(u_id) # Lock it in
        raise ValueError(f"Action '{action_desc}' is disabled for user ID '{u_id}' via {env_var}.")

    # 4. Check Email Match
    if u_email and u_email in protected_set:
        if u_id: cache.add(u_id) # Lock it in for the future!
        print(f"DEBUG: Matched email '{u_email}'. Locking ID {u_id}.")
        raise ValueError(f"Action '{action_desc}' is disabled for user '{u_email}' via {env_var}.")

def register_users_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def get_user_self() -> str:
        """Get current user info"""
        data = await client.request("GET", "users/self")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_user_self(name: str = None, email: str = None) -> str:
        """Update current user account"""
        # Check protection
        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        # 1. Full Protection
        _check_protection(user_item, "HOMEBOX_PROTECTED_USERS", "update_user")

        # 2. Delete Protection (Prevent Email Change)
        # We check if the user is non-deletable. If they are, and they try to change their email,
        # we block it to prevent them from "escaping" the email-based check in a future run.
        if email and email != user_item.get("email"):
             _check_protection(user_item, "HOMEBOX_NON_DELETABLE_USERS", "change_email")

        payload = {}

        if name:
          payload['name'] = name
        if email:
          payload['email'] = email

        # payload = {
        #     "name": name or user_item.get("name"),
        #     "email": email or user_item.get("email")
        # }
        
        data = await client.request("PUT", "users/self", json=payload)
        return f"Updated User: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def change_password(oldPassword: str, newPassword: str) -> str:
        """Change current user password"""
        # Check protection
        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        _check_protection(user_item, "HOMEBOX_PROTECTED_USERS", "change_password")

        payload = {"current": oldPassword, "new": newPassword}
        await client.request("PUT", "users/change-password", json=payload)
        return "Password changed successfully"

    @mcp.tool()
    async def register_user(name: str, email: str, password: str) -> str:
        """Register New User"""
        payload = {"name": name, "email": email, "password": password}
        await client.request("POST", "users/register", json=payload)
        return "User registered successfully"

    @mcp.tool()
    async def login_user(username: str, password: str) -> str:
        """Log in as a different user"""
        await client.login_manual(username, password)
        return f"Logged in as {username}"

    @mcp.tool()
    async def logout_user() -> str:
        """Logout and revert to default user"""
        client.logout()
        return "Logged out. Reverted to default credentials."

    @mcp.tool()
    async def delete_user_self() -> str:
        """Delete Account. Prevent deletion of the primary user defined in environment."""
        # Safety check
        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        u_email = user_item.get("email")
        u_username = user_item.get("username")
        
        # 1. Environment User Protection (Default)
        env_username = os.getenv("HOMEBOX_USERNAME")
        match = False
        if env_username:
            if u_email and u_email == env_username:
                match = True
            elif u_username and u_username == env_username:
                match = True
        
        if match:
             raise ValueError(f"Cannot delete the primary user ({env_username}) defined in environment variables.")
        
        # 2. API Key User Protection
        if os.getenv("HOMEBOX_API_KEY") and client.api_key == os.getenv("HOMEBOX_API_KEY"):
             raise ValueError("Cannot delete the user associated with the environment API Key.")

        # 3. Protected Users (Modifications + Deletion)
        _check_protection(user_item, "HOMEBOX_PROTECTED_USERS", "delete_user")

        # 4. Nondeletable Users (Deletion only)
        _check_protection(user_item, "HOMEBOX_NON_DELETABLE_USERS", "delete_user")

        await client.request("DELETE", "users/self")
        client.logout()
        return "Account deleted successfully. Logged out."
