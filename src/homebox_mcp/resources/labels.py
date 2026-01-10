import json

from fastmcp import FastMCP

from homebox_mcp.client import HomeboxClient


def register_label_resources(mcp: FastMCP, client: HomeboxClient):
    """Register label-related resources."""

    @mcp.resource("homebox://labels")
    async def list_labels_resource() -> str:
        """
        List all labels.
        URI: homebox://labels
        """
        labels = await client.list_labels()
        return json.dumps(labels, indent=2)

    @mcp.resource("homebox://labels/{label_id}")
    async def get_label_resource(label_id: str) -> str:
        """
        Get details for a specific label by its UUID.
        URI: homebox://labels/{uuid}
        """
        label = await client.get_label(label_id)
        if not label:
            return json.dumps({"error": "Label not found", "id": label_id})
        return json.dumps(label, indent=2)
