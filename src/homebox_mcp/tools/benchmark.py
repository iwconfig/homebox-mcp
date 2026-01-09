import os
import json
import logging
from typing import Optional, List, Dict, Any
from ..client import HomeboxClient
from fastmcp import FastMCP, Context

logger = logging.getLogger(__name__)

PROMPTS_DIR = "prompts"

async def handle_benchmark_vision(
    client: HomeboxClient,
    item_ids: Optional[List[str]] = None,
    prompt_version: str = "analyze-item.md",
    ctx: Optional[Context] = None
) -> str:
    """Loads a specific vision prompt version and instructs the agent on how to benchmark it."""
    prompt_path = os.path.join(PROMPTS_DIR, prompt_version)
    if not os.path.exists(prompt_path):
        return f"Error: Prompt version {prompt_version} not found at {prompt_path}"
        
    with open(prompt_path, "r") as f:
        prompt_content = f.read()
        
    if not item_ids:
        # Get some items from inbox as default
        locations = await client.request("GET", "locations", params={"q": "Inbox"})
        inbox_location = next((l for l in locations.get("items", []) if l["name"].lower() == "inbox"), None)
        if inbox_location:
            inbox_items = await client.request("GET", "items", params={"locations": [inbox_location["id"]], "pageSize": 3})
            item_ids = [item["id"] for item in inbox_items.get("items", [])]
            
    output = f"Benchmarking vision prompt version: {prompt_version}\n\n"
    output += "--- PROMPT CONTENT START ---"
    output += prompt_content
    output += "\n--- PROMPT CONTENT END ---"
    output += f"\nTarget Items: {item_ids}\n\n"
    output += "Instruction: Please use the prompt content above to analyze the images of the target items and provide enrichment suggestions."
    
    return output

async def handle_save_prompt_version(
    version_name: str,
    content: str
) -> str:
    """Saves a new version of the analyze-item prompt."""
    if not os.path.exists(PROMPTS_DIR):
        os.makedirs(PROMPTS_DIR)
        
    if not version_name.endswith(".md"):
        version_name += ".md"
        
    path = os.path.join(PROMPTS_DIR, version_name)
    with open(path, "w") as f:
        f.write(content)
        
    return f"Saved prompt version to {path}"


# --- Registration ---

def register_benchmark_tools(mcp: FastMCP, client: HomeboxClient):
    
    @mcp.tool()
    async def benchmark_vision(
        item_ids: Optional[List[str]] = None,
        prompt_version: str = "analyze-item.md",
        ctx: Context = None
    ) -> str:
        """
        Loads a specific vision prompt version and instructs the agent on how to benchmark it against specific items.
        Useful for A/B testing prompt iterations.
        """
        return await handle_benchmark_vision(client, item_ids, prompt_version, ctx)

    @mcp.tool()
    async def save_prompt_version(
        version_name: str,
        content: str
    ) -> str:
        """
        Saves a new version of the analyze-item prompt for benchmarking.
        The filename will be forced to end in .md.
        """
        return await handle_save_prompt_version(version_name, content)
