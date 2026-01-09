from fastmcp import FastMCP

from ..client import HomeboxClient


def register_all_tools(mcp: FastMCP, client: HomeboxClient):
    # Import modules and pass the mcp and client to them
    from . import actions, groups, images, items, labels, locations, maintenance, misc, notifiers, templates, users

    items.register_items_tools(mcp, client)
    locations.register_locations_tools(mcp, client)
    labels.register_labels_tools(mcp, client)
    groups.register_groups_tools(mcp, client)
    misc.register_misc_tools(mcp, client)
    notifiers.register_notifiers_tools(mcp, client)
    actions.register_actions_tools(mcp, client)
    templates.register_templates_tools(mcp, client)
    users.register_users_tools(mcp, client)
    maintenance.register_maintenance_tools(mcp, client)
    images.register_vision_tools(mcp, client)
