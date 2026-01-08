import os
import json
import logging
from mcp.server.fastmcp import FastMCP
from ..client import HomeboxClient

logger = logging.getLogger(__name__)

async def handle_benchmark_vision(
    client: HomeboxClient,
    prompt_version: str = "analyze-item.md",
    item_ids: list[str] | None = None
) -> str:
    """
    Runs the vision optimization benchmark using a specific prompt version.
    
    Args:
        prompt_version: The filename of the prompt template to use (default: analyze-item.md).
                        Must be located in src/homebox_mcp/prompts/templates/ or src/homebox_mcp/prompts/versions/.
        item_ids: Optional list of item IDs (from Homebox) to test against. 
                  If provided, these items act as the "Test Set".
                  If not provided, we should ideally look for local test images (future implementation).
    """
    
    # 1. Resolve Prompt Path
    base_dir = os.path.dirname(os.path.dirname(__file__)) # src/homebox_mcp
    template_dir = os.path.join(base_dir, "prompts", "templates")
    versions_dir = os.path.join(base_dir, "prompts", "versions")
    
    prompt_path = os.path.join(template_dir, prompt_version)
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(versions_dir, prompt_version)
        if not os.path.exists(prompt_path):
             return f"Error: Prompt file '{prompt_version}' not found in templates/ or versions/."
             
    try:
        with open(prompt_path, "r") as f:
            prompt_content = f.read()
    except Exception as e:
        return f"Error reading prompt file: {e}"

    # 2. Prepare the Benchmark Context
    # Since we can't fully "simulate" the agent loop programmatically without complex recursion,
    # this tool acts as a "Prompt Injector" for the USER (you, the Agent).
    # It returns the prompt text + the instructions for YOU to execute the test.
    
    output = f"## 🧪 Vision Benchmark: {prompt_version}\n\n"
    output += "I have loaded the prompt version. Please execute the following logic manually for the Test Set:\n\n"
    
    output += "### 1. The Prompt Logic\n"
    output += "```markdown\n"
    output += prompt_content[:500] + "\n... (truncated) ...\n"
    output += "```\n\n"
    
    if item_ids:
        output += "### 2. The Test Set (Live Items)\n"
        output += "Please run `get_item` and `get_inbox_image` for these IDs, then Apply the Logic above:\n"
        for i, uid in enumerate(item_ids):
            output += f"{i+1}. `{uid}`\n"
            
    else:
        output += "### 2. The Test Set (No Items Provided)\n"
        output += "Please identify items to test, or upload test images to the Inbox.\n"

    return output

def register_benchmark_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def benchmark_vision(
        prompt_version: str = "analyze-item.md",
        item_ids: list[str] | None = None
    ) -> str:
        """
        Loads a specific vision prompt version and instructs the agent on how to benchmark it against specific items.
        Useful for A/B testing prompt iterations.
        """
        return await handle_benchmark_vision(client, prompt_version, item_ids)
