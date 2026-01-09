import json
from ..client import HomeboxClient
from ..guardrails import protect_resource
from fastmcp import FastMCP, Context

# --- Tool Handlers ---

async def handle_list_templates(client: HomeboxClient) -> str:
    """Get All Item Templates."""
    data = await client.request("GET", "templates")
    return json.dumps(data, indent=2)

@protect_resource(resource_type="templates", action="create")
async def handle_create_template(
    client: HomeboxClient,
    name: str,
    description: str | None = None,
    notes: str | None = None,
    defaultName: str | None = None,
    defaultDescription: str | None = None,
    defaultQuantity: int | None = None,
    defaultManufacturer: str | None = None,
    defaultModelNumber: str | None = None,
    defaultLocationId: str | None = None,
    defaultLabelIds: list[str] | None = None,
    defaultInsured: bool = False,
    defaultLifetimeWarranty: bool = False,
    defaultWarrantyDetails: str | None = None,
    includePurchaseFields: bool = False,
    includeSoldFields: bool = False,
    includeWarrantyFields: bool = False
) -> str:
    """Create a new item template for faster data entry."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if notes:
        payload["notes"] = notes
    if defaultName:
        payload["defaultName"] = defaultName
    if defaultDescription:
        payload["defaultDescription"] = defaultDescription
    if defaultQuantity is not None:
        payload["defaultQuantity"] = defaultQuantity
    if defaultManufacturer:
        payload["defaultManufacturer"] = defaultManufacturer
    if defaultModelNumber:
        payload["defaultModelNumber"] = defaultModelNumber
    if defaultLocationId:
        payload["defaultLocationId"] = defaultLocationId
    if defaultLabelIds:
        payload["defaultLabelIds"] = defaultLabelIds
        
    payload.update({
        "defaultInsured": defaultInsured,
        "defaultLifetimeWarranty": defaultLifetimeWarranty
    })
    
    if defaultWarrantyDetails:
        payload["defaultWarrantyDetails"] = defaultWarrantyDetails
        
    payload.update({
        "includePurchaseFields": includePurchaseFields,
        "includeSoldFields": includeSoldFields,
        "includeWarrantyFields": includeWarrantyFields
    })
    
    data = await client.request("POST", "templates", json=payload)
    return f"Created Template: {json.dumps(data, indent=2)}"

async def handle_get_template(client: HomeboxClient, id: str) -> str:
    """Get full details for a specific template by ID."""
    data = await client.request("GET", f"templates/{id}")
    return json.dumps(data, indent=2)

@protect_resource(resource_type="templates", action="update")
async def handle_update_template(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    defaultName: str | None = None,
    defaultDescription: str | None = None,
    defaultQuantity: int | None = None,
    defaultManufacturer: str | None = None,
    defaultModelNumber: str | None = None,
    defaultLocationId: str | None = None,
    defaultLabelIds: list[str] | None = None,
    defaultInsured: bool | None = None,
    defaultLifetimeWarranty: bool | None = None,
    defaultWarrantyDetails: str | None = None,
    includePurchaseFields: bool | None = None,
    includeSoldFields: bool | None = None,
    includeWarrantyFields: bool | None = None
) -> str:
    """Update an existing template."""
    existing = await client.request("GET", f"templates/{id}")
    payload = existing.copy()
    
    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if notes is not None:
        payload["notes"] = notes
    if defaultName is not None:
        payload["defaultName"] = defaultName
    if defaultDescription is not None:
        payload["defaultDescription"] = defaultDescription
    if defaultQuantity is not None:
        payload["defaultQuantity"] = defaultQuantity
    if defaultManufacturer is not None:
        payload["defaultManufacturer"] = defaultManufacturer
    if defaultModelNumber is not None:
        payload["defaultModelNumber"] = defaultModelNumber
    if defaultLocationId is not None:
        payload["defaultLocationId"] = defaultLocationId
    if defaultLabelIds is not None:
        payload["defaultLabelIds"] = defaultLabelIds
    if defaultInsured is not None:
        payload["defaultInsured"] = defaultInsured
    if defaultLifetimeWarranty is not None:
        payload["defaultLifetimeWarranty"] = defaultLifetimeWarranty
    if defaultWarrantyDetails is not None:
        payload["defaultWarrantyDetails"] = defaultWarrantyDetails
    if includePurchaseFields is not None:
        payload["includePurchaseFields"] = includePurchaseFields
    if includeSoldFields is not None:
        payload["includeSoldFields"] = includeSoldFields
    if includeWarrantyFields is not None:
        payload["includeWarrantyFields"] = includeWarrantyFields
        
    data = await client.request("PUT", f"templates/{id}", json=payload)
    return f"Updated Template: {json.dumps(data, indent=2)}"

@protect_resource(resource_type="templates", action="delete")
async def handle_delete_template(client: HomeboxClient, id: str) -> str:
    """Delete a template by ID."""
    await client.request("DELETE", f"templates/{id}")
    return "Deleted Template"

async def handle_create_item_from_template(
    client: HomeboxClient,
    id: str,
    name: str,
    locationId: str,
    quantity: int = 1,
    description: str | None = None,
    labelIds: list[str] | None = None
) -> str:
    """Create a new inventory item using a template as a base."""
    payload = {
        "name": name,
        "locationId": locationId,
        "quantity": quantity
    }
    if description:
        payload["description"] = description
    if labelIds:
        payload["labelIds"] = labelIds
        
    data = await client.request("POST", f"templates/{id}/create-item", json=payload)
    return f"Created Item: {json.dumps(data, indent=2)}"

# --- Registration ---

def register_templates_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool()
    async def list_templates() -> str:
        """Get All Item Templates"""
        return await handle_list_templates(client)

    @mcp.tool()
    async def create_template(
        name: str, description: str | None = None, notes: str | None = None, defaultName: str | None = None,
        defaultDescription: str | None = None, defaultQuantity: int | None = None, defaultManufacturer: str | None = None,
        defaultModelNumber: str | None = None, defaultLocationId: str | None = None, defaultLabelIds: list[str] | None = None,
        defaultInsured: bool = False, defaultLifetimeWarranty: bool = False, defaultWarrantyDetails: str | None = None,
        includePurchaseFields: bool = False, includeSoldFields: bool = False, includeWarrantyFields: bool = False
    ) -> str:
        """Create Item Template"""
        return await handle_create_template(client, name, description, notes, defaultName, defaultDescription, defaultQuantity, defaultManufacturer, defaultModelNumber, defaultLocationId, defaultLabelIds, defaultInsured, defaultLifetimeWarranty, defaultWarrantyDetails, includePurchaseFields, includeSoldFields, includeWarrantyFields)

    @mcp.tool()
    async def get_template(id: str) -> str:
        """Get Item Template"""
        return await handle_get_template(client, id)

    @mcp.tool()
    async def update_template(
        id: str, name: str | None = None, description: str | None = None, notes: str | None = None,
        defaultName: str | None = None, defaultDescription: str | None = None, defaultQuantity: int | None = None,
        defaultManufacturer: str | None = None, defaultModelNumber: str | None = None, defaultLocationId: str | None = None,
        defaultLabelIds: list[str] | None = None, defaultInsured: bool | None = None, defaultLifetimeWarranty: bool | None = None,
        defaultWarrantyDetails: str | None = None, includePurchaseFields: bool | None = None, includeSoldFields: bool | None = None,
        includeWarrantyFields: bool | None = None
    ) -> str:
        """Update Item Template"""
        return await handle_update_template(client, id, name, description, notes, defaultName, defaultDescription, defaultQuantity, defaultManufacturer, defaultModelNumber, defaultLocationId, defaultLabelIds, defaultInsured, defaultLifetimeWarranty, defaultWarrantyDetails, includePurchaseFields, includeSoldFields, includeWarrantyFields)

    @mcp.tool()
    async def delete_template(id: str) -> str:
        """Delete Item Template"""
        return await handle_delete_template(client, id)

    @mcp.tool()
    async def create_item_from_template(id: str, name: str, locationId: str, quantity: int = 1, description: str | None = None, labelIds: list[str] | None = None) -> str:
        """Create Item from Template"""
        return await handle_create_item_from_template(client, id, name, locationId, quantity, description, labelIds)