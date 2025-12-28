import json
from ..client import HomeboxClient
from ..guardrails import protect_resource
from mcp.server.fastmcp import FastMCP

def register_templates_tools(mcp: FastMCP, client: HomeboxClient):

    @mcp.tool()
    async def list_templates() -> str:
        """Get All Item Templates"""
        data = await client.request("GET", "templates")
        return json.dumps(data, indent=2)

    @mcp.tool()
    @protect_resource(resource_type="templates", action="create")
    async def create_template(
        name: str,
        description: str = None,
        notes: str = None,
        defaultName: str = None,
        defaultDescription: str = None,
        defaultQuantity: int = None,
        defaultManufacturer: str = None,
        defaultModelNumber: str = None,
        defaultLocationId: str = None,
        defaultLabelIds: list[str] = None,
        defaultInsured: bool = False,
        defaultLifetimeWarranty: bool = False,
        defaultWarrantyDetails: str = None,
        includePurchaseFields: bool = False,
        includeSoldFields: bool = False,
        includeWarrantyFields: bool = False
    ) -> str:
        """Create Item Template"""
        payload = {"name": name}
        if description: payload["description"] = description
        if notes: payload["notes"] = notes
        if defaultName: payload["defaultName"] = defaultName
        if defaultDescription: payload["defaultDescription"] = defaultDescription
        if defaultQuantity is not None: payload["defaultQuantity"] = defaultQuantity
        if defaultManufacturer: payload["defaultManufacturer"] = defaultManufacturer
        if defaultModelNumber: payload["defaultModelNumber"] = defaultModelNumber
        if defaultLocationId: payload["defaultLocationId"] = defaultLocationId
        if defaultLabelIds: payload["defaultLabelIds"] = defaultLabelIds
        
        payload["defaultInsured"] = defaultInsured
        payload["defaultLifetimeWarranty"] = defaultLifetimeWarranty
        if defaultWarrantyDetails: payload["defaultWarrantyDetails"] = defaultWarrantyDetails
        
        payload["includePurchaseFields"] = includePurchaseFields
        payload["includeSoldFields"] = includeSoldFields
        payload["includeWarrantyFields"] = includeWarrantyFields

        data = await client.request("POST", "templates", json=payload)
        return f"Created Template: {json.dumps(data, indent=2)}"

    @mcp.tool()
    async def get_template(id: str) -> str:
        """Get Item Template"""
        data = await client.request("GET", f"templates/{id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    @protect_resource(resource_type="templates", action="update")
    async def update_template(
        id: str,
        name: str = None,
        description: str = None,
        notes: str = None,
        defaultName: str = None,
        defaultDescription: str = None,
        defaultQuantity: int = None,
        defaultManufacturer: str = None,
        defaultModelNumber: str = None,
        defaultLocationId: str = None,
        defaultLabelIds: list[str] = None,
        defaultInsured: bool = None,
        defaultLifetimeWarranty: bool = None,
        defaultWarrantyDetails: str = None,
        includePurchaseFields: bool = None,
        includeSoldFields: bool = None,
        includeWarrantyFields: bool = None
    ) -> str:
        """Update Item Template"""
        existing = await client.request("GET", f"templates/{id}")
        payload = existing.copy()
        
        if name: payload["name"] = name
        if description is not None: payload["description"] = description
        if notes is not None: payload["notes"] = notes
        if defaultName is not None: payload["defaultName"] = defaultName
        if defaultDescription is not None: payload["defaultDescription"] = defaultDescription
        if defaultQuantity is not None: payload["defaultQuantity"] = defaultQuantity
        if defaultManufacturer is not None: payload["defaultManufacturer"] = defaultManufacturer
        if defaultModelNumber is not None: payload["defaultModelNumber"] = defaultModelNumber
        if defaultLocationId is not None: payload["defaultLocationId"] = defaultLocationId
        if defaultLabelIds is not None: payload["defaultLabelIds"] = defaultLabelIds
        
        if defaultInsured is not None: payload["defaultInsured"] = defaultInsured
        if defaultLifetimeWarranty is not None: payload["defaultLifetimeWarranty"] = defaultLifetimeWarranty
        if defaultWarrantyDetails is not None: payload["defaultWarrantyDetails"] = defaultWarrantyDetails
        
        if includePurchaseFields is not None: payload["includePurchaseFields"] = includePurchaseFields
        if includeSoldFields is not None: payload["includeSoldFields"] = includeSoldFields
        if includeWarrantyFields is not None: payload["includeWarrantyFields"] = includeWarrantyFields

        data = await client.request("PUT", f"templates/{id}", json=payload)
        return f"Updated Template: {json.dumps(data, indent=2)}"

    @mcp.tool()
    @protect_resource(resource_type="templates", action="delete")
    async def delete_template(id: str) -> str:
        """Delete Item Template"""
        await client.request("DELETE", f"templates/{id}")
        return "Deleted Template"

    @mcp.tool()
    async def create_item_from_template(
        id: str, 
        name: str, 
        locationId: str, 
        quantity: int = 1,
        description: str = None,
        labelIds: list[str] = None
    ) -> str:
        """Create Item from Template"""
        payload = {
            "name": name,
            "locationId": locationId, 
            "quantity": quantity
        }
        if description: payload["description"] = description
        if labelIds: payload["labelIds"] = labelIds
        
        data = await client.request("POST", f"templates/{id}/create-item", json=payload)
        return f"Created Item: {json.dumps(data, indent=2)}"
