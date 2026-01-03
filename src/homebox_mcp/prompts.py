from mcp.server.fastmcp import FastMCP

def register_prompts(mcp: FastMCP):
    @mcp.prompt("analyze-item")
    async def analyze_item_prompt(item_id: str = "") -> str:
        """
        Analyze items in the inbox.
        If item_id is provided, analyzes that specific item.
        Otherwise, instructs the agent to check the inbox queue.
        """
        if item_id:
             return (
                f"Please analyze item {item_id}.\n\n"
                "1. Fetch item details (using `get_item`) to find image attachments.\n"
                f"2. Access the image using the resource URI `homebox://items/{{item_id}}/attachments/{{attachment_id}}/image`.\n"
                "3. Identify the object and extract visible text.\n"
                "4. Suggest a Name, Description, and relevant Labels.\n"
                "5. Determine a crop box [left, top, right, bottom] to remove background clutter.\n"
                "6. Use the `crop_item_image` tool to apply the crop.\n"
                "7. Use the `update_item` tool to apply the metadata.\n"
             )
        
        return (
            "Please check the Homebox Inbox for pending items:\n\n"
            "1. Read the resource `homebox://inbox/queue` to get the list of items.\n"
            "2. For each item found with an attachment:\n"
            "   a. Access the image using the provided `resource` URI.\n"
            "   b. Identify the object.\n"
            "   c. Extract visible text (Serial Number, Model, Brand).\n"
            "   d. Suggest a Name, Description, and relevant Labels.\n"
            "   e. Determine a crop box [left, top, right, bottom] to remove background clutter.\n"
            "   f. Use the `crop_item_image` tool to apply the crop.\n"
            "   g. Use the `update_item` tool to apply the metadata.\n"
        )