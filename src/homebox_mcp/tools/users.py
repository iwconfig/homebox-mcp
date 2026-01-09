import os
from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient
from ..guardrails import protect_user_self

# --- Tool Handlers ---


async def handle_get_user_self(client: HomeboxClient) -> dict:
    """Get current user info."""
    return await client.request("GET", "users/self")


@protect_user_self(action_desc="update_user")
async def handle_update_user_self(client: HomeboxClient, name: str | None = None, email: str | None = None) -> dict:
    """Update current user account."""
    existing_res = await client.request("GET", "users/self")
    existing = existing_res.get("item", {})
    payload = {"name": name or existing.get("name", ""), "email": email or existing.get("email", "")}
    return await client.request("PUT", "users/self", json=payload)


@protect_user_self(action_desc="change_password")
async def handle_change_password(client: HomeboxClient, current: str, new: str) -> str:
    """Change current user password."""
    payload = {"current": current, "new": new}
    try:
        await client.request("PUT", "users/change-password", json=payload)
        return "Password changed successfully"
    except Exception as e:
        if "404" in str(e):
            return "Error: Password change endpoint might not be supported in this Homebox version."
        raise e


async def handle_register_user(client: HomeboxClient, name: str, email: str, password: str) -> dict | None:
    """Register New User."""
    if os.getenv("HOMEBOX_ALLOW_USER_REGISTRATION", "false").lower() != "true":
        raise ValueError("User registration is disabled via safety switch (HOMEBOX_ALLOW_USER_REGISTRATION).")

    payload = {"name": name, "email": email, "password": password}
    return await client.request("POST", "users/register", json=payload)


async def handle_login_user(client: HomeboxClient, username: str, password: str) -> str:
    """Log in as a different user."""
    await client.login_manual(username, password)
    return f"Logged in as {username}"


async def handle_logout_user(client: HomeboxClient) -> str:
    """Logout and revert to default user."""
    client.logout()
    return "Logged out successfully"


@protect_user_self(action_desc="delete_user")
async def handle_delete_user_self(client: HomeboxClient) -> str:
    """Delete Account."""
    await client.request("DELETE", "users/self")
    return "Account deleted successfully"


# --- Registration ---


def register_users_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def get_user_self() -> dict:
        """Get current user info"""
        return await handle_get_user_self(client)

    @mcp.tool(output_schema={"type": "object"})
    async def update_user_self(
        name: Annotated[str | None, "New name for the user"] = None,
        email: Annotated[str | None, "New email address for the user"] = None,
    ) -> dict:
        """Update current user account"""
        return await handle_update_user_self(client, name=name, email=email)

    @mcp.tool()
    async def change_password(current: Annotated[str, "Current password"], new: Annotated[str, "New password"]) -> str:
        """Change current user password"""
        return await handle_change_password(client, current=current, new=new)

    @mcp.tool()
    async def register_user(
        name: Annotated[str, "Name for the new user"],
        email: Annotated[str, "Email address for the new user"],
        password: Annotated[str, "Password for the new user"],
    ) -> dict | None:
        """Register New User"""
        return await handle_register_user(client, name=name, email=email, password=password)

    @mcp.tool()
    async def login_user(username: Annotated[str, "Username or email"], password: Annotated[str, "Password"]) -> str:
        """Log in as a different user"""
        return await handle_login_user(client, username, password)

    @mcp.tool()
    async def logout_user() -> str:
        """Logout and revert to default user"""
        return await handle_logout_user(client)

    @mcp.tool()
    async def delete_user_self() -> str:
        """Delete Account. Prevent deletion of protected accounts."""
        return await handle_delete_user_self(client)
