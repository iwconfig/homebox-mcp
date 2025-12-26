import json
import os
from ..client import HomeboxClient
from mcp.server.fastmcp import FastMCP

def register_users_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def get_user_self() -> str:
        """Get current user info"""
        data = await client.request("GET", "users/self")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_user_self(name: str = None, email: str = None) -> str:
        """Update current user account"""
        payload = {}
        if name: payload["name"] = name
        if email: payload["email"] = email
        data = await client.request("PUT", "users/self", json=payload)
        return f"Updated User: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def change_password(oldPassword: str, newPassword: str) -> str:
        """Change current user password"""
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
        u_name = user_item.get("name")
        u_email = user_item.get("email")
        u_username = user_item.get("username")
        
        env_username = os.getenv("HOMEBOX_USERNAME")
        
        # Check if current user matches the environment user
        # Environment user can be username or email. Check both against available fields.
        match = False
        if env_username:
            if u_email and u_email == env_username:
                match = True
            elif u_username and u_username == env_username:
                match = True
        
        if match:
             raise ValueError(f"Cannot delete the primary user ({env_username}) defined in environment variables.")
        
        # Check if we are currently using the environment API key
        if os.getenv("HOMEBOX_API_KEY") and client.api_key == os.getenv("HOMEBOX_API_KEY"):
             raise ValueError("Cannot delete the user associated with the environment API Key.")

        await client.request("DELETE", "users/self")
        client.logout()
        return "Account deleted successfully. Logged out."
        