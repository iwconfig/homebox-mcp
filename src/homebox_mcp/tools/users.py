import json
import os
from ..client import HomeboxClient
from ..guardrails import protect_resource, check_user_protection
from mcp.server.fastmcp import FastMCP

def register_users_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def get_user_self() -> str:
        """Get current user info"""
        data = await client.request("GET", "users/self")
        return json.dumps(data, indent=2)

    @mcp.tool()
    @protect_resource(resource_type="users", action="update")
    async def update_user_self(name: str = None, email: str = None) -> str:
        """Update current user account"""
        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        # 1. Full Protection
        check_user_protection(user_item, "update_user")

        # 2. Delete Protection (Prevent Email Change)
        if email and email != user_item.get("email"):
             check_user_protection(user_item, "change_email")

        payload = {
            "name": name or user_item.get("name"),
            "email": email or user_item.get("email")
        }
        
        data = await client.request("PUT", "users/self", json=payload)
        return f"Updated User: {json.dumps(data, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="users", action="update")
    async def change_password(current: str, new: str) -> str:
        """Change current user password"""
        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        check_user_protection(user_item, "change_password")

        payload = {"current": current, "new": new}
        try:
            await client.request("PUT", "users/change-password", json=payload)
            return "Password changed successfully"
        except Exception as e:
            if "404" in str(e):
                return "Change password endpoint not found (404). This might not be supported in this Homebox version."
            raise

    @mcp.tool()
    @protect_resource(resource_type="users", action="create")
    async def register_user(name: str, email: str, password: str) -> str:
        """Register New User"""
        # Safety Switch: Disabled by default
        if os.getenv("HOMEBOX_ALLOW_USER_REGISTRATION", "").lower() != "true":
            raise ValueError(
                "Safety Lock: 'register_user' is disabled by default. "
                "Set HOMEBOX_ALLOW_USER_REGISTRATION=true to enable."
            )

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
    @protect_resource(resource_type="users", action="delete")
    async def delete_user_self() -> str:
        """Delete Account. Prevent deletion of protected accounts."""
        # Safety Switch: Disabled by default
        if os.getenv("HOMEBOX_ALLOW_USER_DELETION", "").lower() != "true":
            raise ValueError(
                "Safety Lock: 'delete_user_self' is disabled by default. "
                "Set HOMEBOX_ALLOW_USER_DELETION=true to enable."
            )

        current_user = await client.request("GET", "users/self")
        user_item = current_user.get("item", {})
        
        # Guardrail Protection (Primary account, API key, Protected lists)
        check_user_protection(user_item, "delete_user")

        # API Key User Protection
        if os.getenv("HOMEBOX_API_KEY") and client.api_key == os.getenv("HOMEBOX_API_KEY"):
             raise ValueError("Cannot delete the user associated with the environment API Key.")

        await client.request("DELETE", "users/self")
        client.logout()
        return "Account deleted successfully. Logged out."