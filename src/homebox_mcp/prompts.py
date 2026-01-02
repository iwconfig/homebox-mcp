from mcp.server.fastmcp import FastMCP

def register_prompts(mcp: FastMCP):
    @mcp.prompt("analyze-item")
    def analyze_item_prompt(item_summary: str):
        """
        Prompt to analyze an item in the inbox.
        The user should provide the item summary JSON (from homebox://inbox/queue).
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please analyze the following item from the Homebox Inbox:\n\n{item_summary}\n\n"
                        "1. Access the image using the provided resource URI.\n"
                        "2. Identify the object.\n"
                        "3. Extract any visible text (Serial Number, Model, Brand).\n"
                        "4. Suggest a Name, Description, and relevant Labels.\n"
                        "5. Determine a crop box [left, top, right, bottom] to remove background clutter.\n"
                        "6. Use the 'crop_item_image' tool to apply the crop.\n"
                        "7. Use the 'update_item' tool to apply the metadata.\n"
                    )
                }
            }
        ]

