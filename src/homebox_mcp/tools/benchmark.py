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

    output = f"# 🧪 Vision Benchmark: {prompt_version}\n\n"
    output += "## 1. Active Logic\n"
    output += f"```markdown\n{prompt_content}\n```\n\n"
    
    if item_ids:
        output += "## 2. Test Set Evaluation\n"
        output += "I will now summarize the items for you. Please APPLY the logic above to these items.\n\n"
        for uid in item_ids:
            try:
                item = await client.request("GET", f"items/{uid}")
                output += f"### Item: {item.get('name')} (`{uid}`)\n"
                atts = item.get("attachments", [])
                if atts:
                    output += f"- Has {len(atts)} attachments. Use `get_inbox_image(id='{uid}')` to see the photo.\n"
                else:
                    output += "- ⚠️ No attachments found.\n"
            except Exception as e:
                output += f"### Item: `{uid}` (Error: {e})\n"
            output += "\n"
    else:
        output += "## 2. Test Set\nNo items provided. Please identify a failed item to use as a test case.\n"

    output += "\n---\n"
    output += "### 🛠️ Optimization Loop Instructions\n"
    output += "1. Inspect the image(s) using the logic above.\n"
    output += "2. Identify any rotation or crop errors.\n"
    output += "3. If errors found, create a new version using `save_prompt_version`.\n"
    output += "4. Re-run this benchmark with the new version.\n"

    return output

async def handle_save_prompt_version(version_name: str, content: str) -> str:
    """Saves a new prompt version to src/homebox_mcp/prompts/versions/."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    versions_dir = os.path.join(base_dir, "prompts", "versions")
    os.makedirs(versions_dir, exist_ok=True)
    
    file_path = os.path.join(versions_dir, version_name)
    if not file_path.endswith(".md"):
        file_path += ".md"
        
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return f"Successfully saved prompt version to {os.path.basename(file_path)}"
    except Exception as e:
        return f"Error saving prompt version: {e}"

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

    @mcp.tool()
    async def save_prompt_version(version_name: str, content: str) -> str:
        """
        Saves a new version of the analyze-item prompt for benchmarking.
        The filename will be forced to end in .md.
        """
        return await handle_save_prompt_version(version_name, content)
