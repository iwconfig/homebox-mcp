import os
import re
import functools
import inspect
from typing import Set, Optional

def _parse_env_list(env_var_name: str) -> Set[str]:
    """Parses a comma or space separated environment variable into a set of strings."""
    val = os.getenv(env_var_name, "")
    if not val:
        return set()
    parts = re.split(r'[,\s]+', val)
    return {p.strip() for p in parts if p.strip()}

def _is_id_protected(resource_id: str, protected_set: Set[str]) -> bool:
    """Checks if a specific ID is in the protected set (handling 'all')."""
    if not resource_id:
        return False
    if "all" in {s.lower() for s in protected_set}:
        return True
    return resource_id in protected_set

def _is_type_protected(resource_type: str, protected_set: Set[str]) -> bool:
    """Checks if a resource type is in the protected set (handling 'all')."""
    if not resource_type:
        return False
    lower_set = {s.lower() for s in protected_set}
    if "all" in lower_set:
        return True
    return resource_type.lower() in lower_set

def protect_resource(resource_type: str, action: str):
    """
    Decorator to enforce guardrails on MCP tools.
    
    Args:
        resource_type: The name of the resource (e.g., 'items', 'locations', 'labels').
        action: The action being performed ('create', 'update', 'delete').
    
    Checks against:
        - HOMEBOX_READONLY_RESOURCES (blocks create, update, delete)
        - HOMEBOX_NON_DELETABLE_RESOURCES (blocks delete)
        - HOMEBOX_PROTECTED_IDS (blocks update, delete)
        - HOMEBOX_NON_DELETABLE_IDS (blocks delete)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Inspect arguments to find 'id'
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # We look for 'id' argument for ID-based checks
            resource_id = bound_args.arguments.get("id")
            
            # 1. Type-Based Checks
            # READONLY blocks everything
            readonly_types = _parse_env_list("HOMEBOX_READONLY_RESOURCES")
            if _is_type_protected(resource_type, readonly_types):
                 raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_READONLY_RESOURCES.")
            
            # NON_DELETABLE blocks delete
            if action == "delete":
                non_deletable_types = _parse_env_list("HOMEBOX_NON_DELETABLE_RESOURCES")
                if _is_type_protected(resource_type, non_deletable_types):
                     raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_NON_DELETABLE_RESOURCES.")

            # 2. ID-Based Checks (only if we found an ID)
            if resource_id:
                # PROTECTED_IDS blocks update and delete
                if action in ["update", "delete"]:
                    protected_ids = _parse_env_list("HOMEBOX_PROTECTED_IDS")
                    if _is_id_protected(resource_id, protected_ids):
                        raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_PROTECTED_IDS.")
                
                # NON_DELETABLE_IDS blocks delete
                if action == "delete":
                    non_deletable_ids = _parse_env_list("HOMEBOX_NON_DELETABLE_IDS")
                    if _is_id_protected(resource_id, non_deletable_ids):
                         raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_NON_DELETABLE_IDS.")

            return await func(*args, **kwargs)
        return wrapper
    return decorator
