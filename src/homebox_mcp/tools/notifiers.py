from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient

# --- Tool Handlers ---


async def handle_list_notifiers(client: HomeboxClient) -> list[dict]:
    """Get all configured notifiers."""
    return await client.list_notifiers()


async def handle_create_notifier(client: HomeboxClient, name: str, url: str, is_active: bool = True) -> dict:
    """Create a new notification channel (e.g. Discord, Slack, Gotify)."""
    payload = {"name": name, "url": url, "isActive": is_active}
    return await client.create_notifier(payload)


async def handle_test_notifier(client: HomeboxClient, url: str) -> str:
    """Test a notifier URL by sending a sample event."""
    try:
        await client.test_notifier({"url": url})
        return "Notifier test signal sent successfully"
    except Exception as e:
        return f"Error testing notifier: {str(e)}"


async def handle_update_notifier(
    client: HomeboxClient, id: str, name: str | None = None, url: str | None = None, is_active: bool | None = None
) -> dict:
    """Update an existing notifier's configuration."""
    existing_list = await client.list_notifiers()
    notifier = next((n for n in existing_list if n["id"] == id), None)

    if not notifier:
        raise ValueError(f"Notifier {id} not found")

    payload = notifier.copy()
    if name:
        payload["name"] = name
    if url:
        payload["url"] = url
    if is_active is not None:
        payload["isActive"] = is_active

    return await client.update_notifier(id, payload)


async def handle_delete_notifier(client: HomeboxClient, id: str) -> str:
    """Delete a notifier by ID."""
    await client.delete_notifier(id)
    return f"Deleted Notifier {id}"


# --- Registration ---


def register_notifiers_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def list_notifiers() -> dict:
        """Get Notifiers"""
        res = await handle_list_notifiers(client)
        return {"notifiers": res}

    @mcp.tool(output_schema={"type": "object"})
    async def create_notifier(
        name: Annotated[str, "Name of the notifier"],
        url: Annotated[str, "URL of the notifier"],
        is_active: Annotated[bool, "Whether the notifier is enabled"] = True,
    ) -> dict:
        """Create Notifier"""
        return await handle_create_notifier(client, name=name, url=url, is_active=is_active)

    @mcp.tool()
    async def test_notifier(url: Annotated[str, "URL to test"]) -> str:
        """Test Notifier"""
        return await handle_test_notifier(client, url=url)

    @mcp.tool(output_schema={"type": "object"})
    async def update_notifier(
        id: Annotated[str, "ID of the notifier"],
        name: Annotated[str | None, "New name of the notifier"] = None,
        url: Annotated[str | None, "New URL of the notifier"] = None,
        is_active: Annotated[bool | None, "Whether the notifier is enabled"] = None,
    ) -> dict:
        """Update Notifier"""
        return await handle_update_notifier(client, id=id, name=name, url=url, is_active=is_active)

    @mcp.tool()
    async def delete_notifier(id: Annotated[str, "ID of the notifier"]) -> str:
        """Delete a Notifier"""
        return await handle_delete_notifier(client, id=id)
