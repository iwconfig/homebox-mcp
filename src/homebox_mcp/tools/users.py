import json
import os
from ..client import HomeboxClient
from ..guardrails import protect_resource, check_user_protection
from fastmcp import FastMCP

# --- Tool Handlers ---

async def handle_get_user_self(client: HomeboxClient) -> str:
    """Get current user information."""
    data = await client.request("GET", "users/self")
    return json.dumps(data, indent=2)

@protect_resource(resource_type="users", action="update")
async def handle_update_user_self(client: HomeboxClient, name: str | None = None, email: str | None = None) -> str:
    """Update current user's profile metadata."""
    current_user = await client.request("GET", "users/self")
    user_item = current_user.get("item", {})
    
    # Check if the account is protected from modifications
    check_user_protection(user_item, "update_user")
    
    # Check if we are changing the email (which is a form of deletion protection)
    if email and email != user_item.get("email"):
        check_user_protection(user_item, "change_email")
        
    payload = {
        "name": name or user_item.get("name"),
        "email": email or user_item.get("email")
    }
    
    data = await client.request("PUT", "users/self", json=payload)
    return f"Updated User: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="users", action="update")
async def handle_change_password(client: HomeboxClient, current: str, new: str) -> str:
    """Change current user's password."""
    current_user = await client.request("GET", "users/self")
    check_user_protection(current_user.get("item", {}), "change_password")
    
    try:
        await client.request("PUT", "users/change-password", json={"current": current, "new": new})
        return "Password changed successfully"
    except Exception as e:
        if "404" in str(e):
            return "Change password endpoint not found (404). This might not be supported in this Homebox version."
        raise

@protect_resource(resource_type="users", action="create")
async def handle_register_user(client: HomeboxClient, name: str, email: str, password: str) -> str:
    """Register a new user account."""
    if os.getenv("HOMEBOX_ALLOW_USER_REGISTRATION", "").lower() != "true":
        raise ValueError("Safety Lock: 'register_user' is disabled by default. Set HOMEBOX_ALLOW_USER_REGISTRATION=true to enable.")
        
    await client.request("POST", "users/register", json={"name": name, "email": email, "password": password})
    return "User registered successfully"

async def handle_login_user(client: HomeboxClient, username: str, password: str) -> str:
    """Manually switch the authenticated user session."""
    await client.login_manual(username, password)
    return f"Logged in as {username}"

async def handle_logout_user(client: HomeboxClient) -> str:
    """Logout and revert to the default environment credentials."""
    client.logout()
    return "Logged out. Reverted to default credentials."

@protect_resource(resource_type="users", action="delete")
async def handle_delete_user_self(client: HomeboxClient) -> str:
    """Permanently delete the current user's account."""
    if os.getenv("HOMEBOX_ALLOW_USER_DELETION", "").lower() != "true":
        raise ValueError("Safety Lock: 'delete_user_self' is disabled by default. Set HOMEBOX_ALLOW_USER_DELETION=true to enable.")
        
    current_user = await client.request("GET", "users/self")
    check_user_protection(current_user.get("item", {}), "delete_user")
    
    # Prevent deletion if the user is the one associated with the master API Key
    if os.getenv("HOMEBOX_API_KEY") and client.api_key == os.getenv("HOMEBOX_API_KEY"):
         raise ValueError("Cannot delete the user associated with the environment API Key.")
         
    await client.request("DELETE", "users/self")
    client.logout()
    return "Account deleted successfully. Logged out."

# --- Registration ---

def register_users_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def get_user_self() -> str:
        """Get current user info"""
        return await handle_get_user_self(client)

    @mcp.tool()
    async def update_user_self(name: str | None = None, email: str | None = None) -> str:
        """Update current user account"""
        return await handle_update_user_self(client, name, email)

    @mcp.tool()
    async def change_password(current: str, new: str) -> str:
        """Change current user password"""
        return await handle_change_password(client, current, new)

    @mcp.tool()
    async def register_user(name: str, email: str, password: str) -> str:
        """Register New User"""
        return await handle_register_user(client, name, email, password)

    @mcp.tool()
    async def login_user(username: str, password: str) -> str:
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
