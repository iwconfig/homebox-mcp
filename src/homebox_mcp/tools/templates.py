from typing import Annotated

from fastmcp import FastMCP

from ..client import HomeboxClient
from ..guardrails import protect_resource

# --- Tool Handlers ---


async def handle_list_templates(client: HomeboxClient) -> list[dict]:
    """Get All Item Templates."""
    return await client.list_templates()


@protect_resource(resource_type="templates", action="create")
async def handle_create_template(
    client: HomeboxClient,
    name: str,
    description: str | None = None,
    notes: str | None = None,
    default_name: str | None = None,
    default_description: str | None = None,
    default_quantity: int | None = None,
    default_manufacturer: str | None = None,
    default_model_number: str | None = None,
    default_location_id: str | None = None,
    default_label_ids: list[str] | None = None,
    default_insured: bool = False,
    default_lifetime_warranty: bool = False,
    default_warranty_details: str | None = None,
    include_purchase_fields: bool = False,
    include_sold_fields: bool = False,
    include_warranty_fields: bool = False,
) -> dict:
    """Create a new item template for faster data entry."""
    payload = {"name": name}
    if description:
        payload["description"] = description
    if notes:
        payload["notes"] = notes
    if default_name:
        payload["defaultName"] = default_name
    if default_description:
        payload["defaultDescription"] = default_description
    if default_quantity is not None:
        payload["defaultQuantity"] = default_quantity
    if default_manufacturer:
        payload["defaultManufacturer"] = default_manufacturer
    if default_model_number:
        payload["defaultModelNumber"] = default_model_number
    if default_location_id:
        payload["defaultLocationId"] = default_location_id
    if default_label_ids:
        payload["defaultLabelIds"] = default_label_ids

    payload.update({"defaultInsured": default_insured, "defaultLifetimeWarranty": default_lifetime_warranty})

    if default_warranty_details:
        payload["defaultWarrantyDetails"] = default_warranty_details

    payload.update(
        {
            "includePurchaseFields": include_purchase_fields,
            "includeSoldFields": include_sold_fields,
            "includeWarrantyFields": include_warranty_fields,
        }
    )

    return await client.create_template(payload)


async def handle_get_template(client: HomeboxClient, id: str) -> dict:
    """Get full details for a specific template by ID."""
    return await client.get_template(id)


@protect_resource(resource_type="templates", action="update")
async def handle_update_template(
    client: HomeboxClient,
    id: str,
    name: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    default_name: str | None = None,
    default_description: str | None = None,
    default_quantity: int | None = None,
    default_manufacturer: str | None = None,
    default_model_number: str | None = None,
    default_location_id: str | None = None,
    default_label_ids: list[str] | None = None,
    default_insured: bool | None = None,
    default_lifetime_warranty: bool | None = None,
    default_warranty_details: str | None = None,
    include_purchase_fields: bool | None = None,
    include_sold_fields: bool | None = None,
    include_warranty_fields: bool | None = None,
) -> dict:
    """Update an existing template."""
    existing = await client.get_template(id)
    payload = existing.copy()

    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if notes is not None:
        payload["notes"] = notes
    if default_name is not None:
        payload["defaultName"] = default_name
    if default_description is not None:
        payload["defaultDescription"] = default_description
    if default_quantity is not None:
        payload["defaultQuantity"] = default_quantity
    if default_manufacturer is not None:
        payload["defaultManufacturer"] = default_manufacturer
    if default_model_number is not None:
        payload["defaultModelNumber"] = default_model_number
    if default_location_id is not None:
        payload["defaultLocationId"] = default_location_id
    if default_label_ids is not None:
        payload["defaultLabelIds"] = default_label_ids
    if default_insured is not None:
        payload["defaultInsured"] = default_insured
    if default_lifetime_warranty is not None:
        payload["defaultLifetimeWarranty"] = default_lifetime_warranty
    if default_warranty_details is not None:
        payload["defaultWarrantyDetails"] = default_warranty_details
    if include_purchase_fields is not None:
        payload["includePurchaseFields"] = include_purchase_fields
    if include_sold_fields is not None:
        payload["includeSoldFields"] = include_sold_fields
    if include_warranty_fields is not None:
        payload["includeWarrantyFields"] = include_warranty_fields

    return await client.update_template(id, payload)


@protect_resource(resource_type="templates", action="delete")
async def handle_delete_template(client: HomeboxClient, id: str) -> str:
    """Delete a template by ID."""
    await client.delete_template(id)
    return f"Deleted Template {id}"


async def handle_create_item_from_template(
    client: HomeboxClient,
    id: str,
    name: str,
    location_id: str,
    quantity: int = 1,
    description: str | None = None,
    label_ids: list[str] | None = None,
) -> dict:
    """Create a new inventory item using a template as a base."""
    payload = {"name": name, "locationId": location_id, "quantity": quantity}
    if description:
        payload["description"] = description
    if label_ids:
        payload["labelIds"] = label_ids

    return await client.create_item_from_template(id, payload)


# --- Registration ---


def register_templates_tools(mcp: FastMCP, client: HomeboxClient):
    @mcp.tool(output_schema={"type": "object"})
    async def list_templates() -> dict:
        """Get All Item Templates"""
        res = await handle_list_templates(client)
        return {"templates": res}

    @mcp.tool(output_schema={"type": "object"})
    async def create_template(
        name: Annotated[str, "Name for the template"],
        description: Annotated[str | None, "Description for the template"] = None,
        notes: Annotated[str | None, "Internal notes"] = None,
        default_name: Annotated[str | None, "Default item name"] = None,
        default_description: Annotated[str | None, "Default item description"] = None,
        default_quantity: Annotated[int | None, "Default item quantity"] = None,
        default_manufacturer: Annotated[str | None, "Default manufacturer"] = None,
        default_model_number: Annotated[str | None, "Default model number"] = None,
        default_location_id: Annotated[str | None, "Default location UUID"] = None,
        default_label_ids: Annotated[list[str] | None, "List of default label UUIDs"] = None,
        default_insured: Annotated[bool, "Whether item is insured by default"] = False,
        default_lifetime_warranty: Annotated[bool, "Whether item has lifetime warranty"] = False,
        default_warranty_details: Annotated[str | None, "Default warranty details"] = None,
        include_purchase_fields: Annotated[bool, "Whether to show purchase fields"] = False,
        include_sold_fields: Annotated[bool, "Whether to show sold fields"] = False,
        include_warranty_fields: Annotated[bool, "Whether to show warranty fields"] = False,
    ) -> dict:
        """Create Item Template"""
        return await handle_create_template(
            client,
            name=name,
            description=description,
            notes=notes,
            default_name=default_name,
            default_description=default_description,
            default_quantity=default_quantity,
            default_manufacturer=default_manufacturer,
            default_model_number=default_model_number,
            default_location_id=default_location_id,
            default_label_ids=default_label_ids,
            default_insured=default_insured,
            default_lifetime_warranty=default_lifetime_warranty,
            default_warranty_details=default_warranty_details,
            include_purchase_fields=include_purchase_fields,
            include_sold_fields=include_sold_fields,
            include_warranty_fields=include_warranty_fields,
        )

    @mcp.tool(output_schema={"type": "object"})
    async def get_template(id: Annotated[str, "ID of the template"]) -> dict:
        """Get Item Template"""
        return await handle_get_template(client, id=id)

    @mcp.tool(output_schema={"type": "object"})
    async def update_template(
        id: Annotated[str, "ID of the template"],
        name: Annotated[str | None, "New name for the template"] = None,
        description: Annotated[str | None, "New description for the template"] = None,
        notes: Annotated[str | None, "New internal notes"] = None,
        default_name: Annotated[str | None, "New default item name"] = None,
        default_description: Annotated[str | None, "New default item description"] = None,
        default_quantity: Annotated[int | None, "New default item quantity"] = None,
        default_manufacturer: Annotated[str | None, "New default manufacturer"] = None,
        default_model_number: Annotated[str | None, "New default model number"] = None,
        default_location_id: Annotated[str | None, "New default location UUID"] = None,
        default_label_ids: Annotated[list[str] | None, "New list of default label UUIDs"] = None,
        default_insured: Annotated[bool | None, "New default insured status"] = None,
        default_lifetime_warranty: Annotated[bool | None, "New default lifetime warranty status"] = None,
        default_warranty_details: Annotated[str | None, "New default warranty details"] = None,
        include_purchase_fields: Annotated[bool | None, "New purchase fields visibility"] = None,
        include_sold_fields: Annotated[bool | None, "New sold fields visibility"] = None,
        include_warranty_fields: Annotated[bool | None, "New warranty fields visibility"] = None,
    ) -> dict:
        """Update Item Template"""
        return await handle_update_template(
            client,
            id=id,
            name=name,
            description=description,
            notes=notes,
            default_name=default_name,
            default_description=default_description,
            default_quantity=default_quantity,
            default_manufacturer=default_manufacturer,
            default_model_number=default_model_number,
            default_location_id=default_location_id,
            default_label_ids=default_label_ids,
            default_insured=default_insured,
            default_lifetime_warranty=default_lifetime_warranty,
            default_warranty_details=default_warranty_details,
            include_purchase_fields=include_purchase_fields,
            include_sold_fields=include_sold_fields,
            include_warranty_fields=include_warranty_fields,
        )

    @mcp.tool()
    async def delete_template(id: Annotated[str, "ID of the template"]) -> str:
        """Delete Item Template"""
        return await handle_delete_template(client, id=id)

    @mcp.tool(output_schema={"type": "object"})
    async def create_item_from_template(
        id: Annotated[str, "ID of the template"],
        name: Annotated[str, "Name for the new item"],
        location_id: Annotated[str, "ID of the location"],
        quantity: Annotated[int, "Quantity of the new item"] = 1,
        description: Annotated[str | None, "Description for the new item"] = None,
        label_ids: Annotated[list[str] | None, "List of label UUIDs"] = None,
    ) -> dict:
        """Create Item from Template"""
        return await handle_create_item_from_template(
            client,
            id=id,
            name=name,
            location_id=location_id,
            quantity=quantity,
            description=description,
            label_ids=label_ids,
        )
