from mcp.server.fastmcp import FastMCP

import os



def register_prompts(mcp: FastMCP):

    @mcp.prompt("analyze-item")

    async def analyze_item_prompt(item_id: str = "") -> str:

        """

        Analyze items in the inbox.

        If item_id is provided, analyzes that specific item.

        Otherwise, instructs the agent to check the inbox queue.

        """

        # Load the prompt template from file

        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "templates", "analyze-item.md")

        # Fallback for different execution environments

        if not os.path.exists(prompt_path):

             prompt_path = os.path.join(os.path.dirname(__file__), "templates", "analyze-item.md")



        try:

            with open(prompt_path, "r") as f:

                base_prompt = f.read()

        except Exception as e:

            return f"Error loading prompt template: {str(e)}"



        if item_id:

             return (

                f"Please analyze item {item_id}.\n\n"

                "1. Fetch item details (using `get_item`) to find image attachments.\n"

                f"2. Access the image using the resource URI `homebox://items/{{item_id}}/attachments/{{attachment_id}}/image`.\n"

                "3. Identify the object and extract visible text.\n"

                "4. Suggest a Name, Description, and relevant Labels.\n"

                "5. Determine a crop box [left, top, right, bottom] in normalized 0-1000 coordinates to remove background clutter.\n"

                "6. Use the `crop_item_image` tool to apply the crop.\n"

                "7. Use the `update_item` tool to apply the metadata.\n"

             )

        

        return base_prompt
