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
            "# CONTEXT\n"
            "You are an intelligent inventory management assistant for a Homebox instance. "
            "Your goal is to process the 'Inbox' queue, identifying items from photos and organizing them into the correct locations.\n\n"
            
            "# OBJECTIVE\n"
            "Analyze pending items from the Inbox (both server-side and local files), identify them, enriched them with metadata, "
            "and move them to their permanent storage locations.\n\n"

            "# STYLE\n"
            "Strict, deterministic, and structured. Do not guess. If information is missing, leave it blank or mark for review.\n\n"

            "# RULES (STRICT)\n"
            "1. **Visual Chain-of-Thought (VCoT)**: BEFORE calling any tools, you MUST explain your visual reasoning. Identify every object in the image, estimate its coordinates, and determine its rotation angle (if not level).\n"
            "2. **Identity Rule**: If an item is generic (e.g., 'Wooden Spoon'), DO NOT invent a brand. Leave `manufacturer` and `modelNumber` empty.\n"
            "3. **Location Strategy**:\n"
            "   - **Unhomed Items** (in 'Inbox'): Move them to the most appropriate location found in the `get_inbox_queue` context.\n"
            "   - **Pre-Categorized Items**: If an item is already in a valid location (not Inbox), PRESERVE that location ID. Do not move it unless explicitly asked.\n"
            "   - **Sub-Items**: If an item is a part of another (is_child), it MUST inherit the parent's location.\n"
            "4. **Orientation Precision**: EVERY object cutout MUST be perfectly level (upright). Positive degrees rotate **Counter-Clockwise**. Negative degrees rotate **Clockwise**.\n"
            "   - **The Leveling Rule**: Estimate the angle required to make the object's primary axis (or text) perfectly vertical or horizontal. If an item is tilted 15 degrees Clockwise, you need to rotate it 15 degrees **Counter-Clockwise** (Value: `15`).\n"
            "5. **Centering & Cropping**: Ensure `crop_box` is tight around the object but with enough padding to keep it centered. You may use **normalized coordinates (0-1000)** for convenience; the tool will automatically scale them to the image's actual pixels.\n"
            "6. **Mixed Sets**: If an image contains multiple distinct objects, use the `extracted_objects` parameter in `finalize_processed_item`. Each object MUST have its own `crop_box` and MUST have an estimated `rotation` to ensure it is upright.\n"
            "7. **Batch Mode**: Execute `get_inbox_image` and identification steps in parallel where possible.\n"
            "8. **Negative Signal**: If a field (like Serial Number) is not visible, do not hallucinate 'N/A' or 'Unknown'. Send `None` (null).\n\n"

            "# FEW-SHOT EXAMPLES (GOLDEN)\n\n"
            
            "## Example 1: The Branded Product\n"
            "**Input**: Image of a 'Bosch PSB 1800' drill.\n"
            "**Visual Reasoning**: I see a green power drill tilted about 10 degrees Clockwise. I identify 'Bosch' branding and 'PSB 1800' model text. Coordinates: [100, 200, 800, 600]. To level it, I need a 10 degree Counter-Clockwise rotation.\n"
            "**Action**:\n"
            "- Name: 'Bosch PSB 1800 Drill'\n"
            "- Manufacturer: 'Bosch'\n"
            "- Model: 'PSB 1800'\n"
            "- Rotation: 10\n"
            "- Location: 'Garage > Power Tools' (ID: uuid-garage-tools)\n"
            "- Tool Call: `finalize_processed_item(..., rotation=10, locationId='uuid-garage-tools')`\n\n"

            "## Example 2: The Mixed Set (Extraction with VCoT)\n"
            "**Input**: Image containing a Hammer and a Tilted Screwdriver.\n"
            "**Visual Reasoning**: I see two objects. Object 1 is a hammer at [50, 50, 400, 300], level (0 deg). Object 2 is a screwdriver at [450, 50, 900, 300], rotated about 45 degrees Clockwise. To level it, I need a 45 degree Counter-Clockwise rotation.\n"
            "**Action**:\n"
            "- Object 1: 'Claw Hammer', crop_box: [50, 50, 400, 300], rotation: 0\n"
            "- Object 2: 'Phillips Screwdriver', crop_box: [450, 50, 900, 300], rotation: 45\n"
            "- Tool Call: `finalize_processed_item(..., extracted_objects=[{'name': 'Claw Hammer', 'crop_box': [50, 50, 400, 300], 'rotation': 0}, {'name': 'Phillips Screwdriver', 'crop_box': [450, 50, 900, 300], 'rotation': 45}])`\n\n"

            "## Example 3: The Pre-Categorized Item\n"
            "**Input**: Item 'HDMI Cable' currently located in 'Office > Cable Bin'.\n"
            "**Action**:\n"
            "- Analysis: Item is already correctly placed.\n"
            "- Location: PRESERVE 'Office > Cable Bin'.\n"
            "- Tool Call: `finalize_processed_item(..., locationId='uuid-office-cables')` (Matches current location)\n\n"

            "# INSTRUCTIONS\n"
            "1. **Get the Queue**: Run `get_inbox_queue` to see all pending items.\n"
            "2. **Process**: For each item, fetch the image (`get_inbox_image`), identify it, and determine the target location.\n"
            "3. **Finalize**: Call `finalize_processed_item` with the **Strict Types** required (e.g., `source` must be 'homebox' or 'local').\n"
        )