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
                "5. Determine a crop box [left, top, right, bottom] in normalized 0-1000 coordinates to remove background clutter.\n"
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
            "Strict, deterministic, and structured. Do not guess.\n\n"

            "# RULES (STRICT)\n"
            "1. **Visual Chain-of-Thought (VCoT)**: BEFORE calling any tools, you MUST explain your visual reasoning:\n"
            "   - **Identify**: List every object and its normalized coordinates [left, top, right, bottom] (0-1000).\n"
            "   - **Reading Direction Vector**: Pick the most prominent word (e.g., brand name). State its Start and End coordinates: 'Word [NAME] starts at [x, y] and ends at [x, y]'.\n"
            "   - **Determine Orientation**: Based on the vector, state the current reading direction (e.g., 'Text reads Bottom-to-Top').\n"
            "   - **Calculate Rotation**: Use the Mapping Table below to find the degrees needed to make the text read Left-to-Right. **Positive = Counter-Clockwise (CCW)**.\n\n"

            "2. **Rotation Mapping Table (Target: Left-to-Right)**\n"
            "   | Current Reading Direction | CCW Rotation Required |\n"
            "   | :--- | :--- |\n"
            "   | Horizontal (Left-to-Right) | 0° |\n"
            "   | Vertical (Top-to-Bottom) | 90° |\n"
            "   | Horizontal (Right-to-Left) | 180° |\n"
            "   | Vertical (Bottom-to-Top) | 270° |\n\n"

            "3. **Semantic Upright (The Readability Rule)**: EVERY object cutout MUST be semantically upright and readable.\n"
            "   - **Text Trumps Shape**: If an object is physically vertical but its text is vertical/upside down, you MUST rotate it to make the text horizontal (L-R).\n"
            "   - **Symmetry**: For items without text, use functional features (nozzles, lids, terminals) as the 'Top' and align to 12 o'clock.\n\n"

            "4. **Location Strategy**:\n"
            "   - **Unhomed Items** (in 'Inbox'): Move them to the most appropriate location found in the `get_inbox_queue` context.\n"
            "   - **Pre-Categorized Items**: Preserve current location ID.\n\n"

            "5. **Centering & Padding**: Ensure `crop_box` is tight but includes enough padding to prevent clipping after rotation.\n\n"

            "6. **Negative Signal**: If a field is not visible, send `None` (null). Do not hallucinate.\n\n"

            "# FEW-SHOT EXAMPLES (GOLDEN)\n\n"
            
            "## Example: The Horizontal Can\n"
            "**Input**: Image of a spray can lying horizontally with the nozzle on the right.\n"
            "**Visual Reasoning**:\n"
            "- Identify: Spray can at [100, 400, 500, 600].\n"
            "- Reading Vector: Word 'CLEANER' starts at [400, 450] and ends at [200, 450].\n"
            "- Orientation: Text reads Right-to-Left.\n"
            "- Calculate Rotation: Per table, R-L requires 180° CCW.\n"
            "**Action**: `finalize_processed_item(..., extracted_objects=[{'name': 'Cleaner', 'crop_box': [100, 400, 500, 600], 'rotation': 180}])`\n\n"

            "# INSTRUCTIONS\n"
            "1. Run `get_inbox_queue` to see pending items.\n"
            "2. For each, fetch image (`get_inbox_image`), perform VCoT, and determine location.\n"
            "3. Finalize using `finalize_processed_item` with normalized coordinates.\n"
        )