import httpx
from fastmcp import Context
from ..client import HomeboxClient

async def fuzzy_resolve_id(
    client: HomeboxClient,
    resource_type: str,
    identifier: str,
    ctx: Context | None = None,
    target_name: str | None = None,
) -> str:
    """
    Attempts to resolve an identifier (ID or Name) to a valid UUID.
    If identifier is not a valid UUID (causes 404 or 400), it searches for a resource
    of resource_type with a similar name and uses sampling to confirm with the user.
    """
    try:
        if resource_type == "locations":
            await client.get_location(identifier)
        elif resource_type == "labels":
            await client.get_label(identifier)
        elif resource_type == "items":
            await client.get_item(identifier)
        return identifier
    except httpx.HTTPStatusError as e:
        if e.response.status_code in [400, 404] and ctx:
            suggestions = await _fuzzy_find(client, resource_type, identifier)
            if not suggestions:
                raise e
                
            res_kind = resource_type.rstrip('s')
            
            # 1. Single match -> Sampling (YES/NO)
            if len(suggestions) == 1:
                suggestion = suggestions[0]
                prompt = (
                    f"I couldn't find a {res_kind} with identifier '{identifier}', "
                    f"but I found a match: '{suggestion['name']}' ({suggestion['id']}).\n"
                    f"Should I use this {res_kind}"
                )
                if target_name:
                    prompt += f" for '{target_name}'?"
                else:
                    prompt += "?"

                sample_res = await ctx.sample(
                    messages=[prompt],
                    system_prompt=(
                        f"You are an inventory assistant. The user provided an invalid {res_kind} identifier. "
                        "Respond with 'YES' to use the suggestion, or 'NO' to fail."
                    ),
                    max_tokens=10
                )

                if "YES" in sample_res.text.upper():
                    return suggestion["id"]
            
            # 2. Multiple matches -> Elicitation (Selection)
            else:
                # Prepare selection options for elicit
                # We'll map the display string back to the UUID
                options_map = {f"{s['name']} ({s['id']})": s["id"] for s in suggestions[:10]}
                options_list = list(options_map.keys())
                
                # Use elicitation for structured choice if supported
                prompt = f"Multiple matches found for {res_kind} '{identifier}'. Which one should I use?"
                try:
                    elicit_res = await ctx.elicit(
                        message=prompt,
                        response_type=options_list
                    )
                    # Check if the elicitation was accepted and we got a valid response
                    # In FastMCP 2.0+, AcceptedElicitation contains the response
                    from fastmcp.server.context import AcceptedElicitation
                    if isinstance(elicit_res, AcceptedElicitation):
                        selected_text = elicit_res.data
                        if selected_text in options_map:
                            return options_map[selected_text]
                except Exception:
                    # Fallback to sampling if elicitation is not supported or fails
                    options_str = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options_list)])
                    prompt_alt = f"{prompt}\n\n{options_str}\n\nRespond with the number (1-{len(options_list)}) or 'NONE'."
                    sample_res = await ctx.sample(messages=[prompt_alt], max_tokens=10)
                    import re
                    match = re.search(r"(\d+)", sample_res.text)
                    if match:
                        idx = int(match.group(1)) - 1
                        if 0 <= idx < len(options_list):
                            return options_map[options_list[idx]]
        
        raise e

async def _fuzzy_find(client: HomeboxClient, resource_type: str, query: str) -> list[dict]:
    """Helper to find resources by name (case-insensitive partial match)."""
    try:
        resources = []
        if resource_type == "locations":
            resources = await client.list_locations()
        elif resource_type == "labels":
            resources = await client.list_labels()
        elif resource_type == "items":
            res = await client.list_items(q=query)
            resources = res.get("items", [])
            
        query = query.lower()
        matches = []
        for res in resources:
            if query in res["name"].lower():
                matches.append(res)
        return matches
    except Exception:
        return []

def ensure_required_fields(payload: dict) -> dict:
    """
    Ensures that mandatory date and string fields are present in the payload
    to satisfy Homebox's strict JSON unmarshaling.
    """
    updated = payload.copy()
    
    # Mandatory string fields
    for key in ["purchaseFrom", "soldTo", "soldNotes", "warrantyDetails"]:
        if key not in updated:
            updated[key] = ""
            
    # Mandatory date fields (Go zero-time)
    for key in ["purchaseTime", "soldTime", "warrantyExpires"]:
        if not updated.get(key):
            updated[key] = "0001-01-01T00:00:00Z"
            
    return updated

def flatten_object_refs(item: dict) -> dict:
    """
    Converts nested object references (from GET responses) into flat ID fields
    suitable for PUT/POST payloads.
    """
    flattened = item.copy()
    
    if loc := item.get("location"):
        flattened["locationId"] = loc["id"]
        
    if parent := item.get("parent"):
        flattened["parentId"] = parent["id"]
        
    if labels := item.get("labels"):
        flattened["labelIds"] = [label["id"] for label in labels]
        
    return flattened