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
            suggestion = await _fuzzy_find(client, resource_type, identifier)
            if suggestion:
                res_kind = resource_type.rstrip('s')
                prompt = (
                    f"I couldn't find a {res_kind} with identifier '{identifier}', "
                    f"but I found a similar {res_kind}: '{suggestion['name']}' ({suggestion['id']}).\n"
                    f"Should I use this {res_kind} instead"
                )
                if target_name:
                    prompt += f" for '{target_name}'?"
                else:
                    prompt += "?"

                sample_res = await ctx.sample(
                    messages=[prompt],
                    system_prompt=(
                        f"You are an inventory assistant. The user provided an invalid {res_kind} identifier. "
                        "Determine if the suggested resource is a reasonable substitute. "
                        "Respond with 'YES' to use the suggestion, or 'NO' to fail the operation."
                    ),
                    max_tokens=10
                )

                if "YES" in sample_res.text.upper():
                    await ctx.info(f"Using suggested {res_kind} '{suggestion['name']}' instead.")
                    return suggestion["id"]
        
        raise e

async def _fuzzy_find(client: HomeboxClient, resource_type: str, query: str) -> dict | None:
    """Helper to find a resource by name (case-insensitive partial match)."""
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
        for res in resources:
            if query in res["name"].lower():
                return res
    except Exception:
        pass
    return None

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