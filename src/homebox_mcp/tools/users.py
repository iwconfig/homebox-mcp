import json
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
        payload = {"oldPassword": oldPassword, "newPassword": newPassword}
        await client.request("PUT", "users/change-password", json=payload)
        return "Password changed successfully"

    @mcp.tool()
    async def register_user(name: str, email: str, password: str) -> str:
        """Register New User"""
        payload = {"name": name, "email": email, "password": password}
        await client.request("POST", "users/register", json=payload)
        return "User registered successfully"
