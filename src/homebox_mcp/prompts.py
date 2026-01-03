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
            "Please check for pending items requiring processing:\n\n"
            "### Instructions\n"
            "1. **Get the Queue**: Run `get_inbox_queue` to see all items requiring processing (from server and local files).\n"
            "2. **Process in Parallel**: You can process multiple items simultaneously for efficiency.\n"
            "3. **Analyze and Finalize** for each item:\n"
            "   a. Access the image using `get_inbox_image` (pass `id` and `attachment_id` from the queue).\n"
            "   b. Identify the object and extract text (Serial, Model, Brand).\n"
            "   c. Use `finalize_processed_item` to apply metadata AND move the item out of the Inbox to its permanent location.\n"
            "      - Set `source` correctly based on the queue (usually 'local' or 'homebox').\n"
            "      - DO NOT leave processed items in the 'Inbox' location.\n"
        )