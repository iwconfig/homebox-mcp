import os
import re
import functools
import inspect
from typing import Set

# Cache to remember IDs that matched protected emails during this process lifecycle
# This prevents redundant lookups and ensures consistency if a user's email changes
_PROTECTED_ID_CACHE: set[str] = set()
_NON_DELETABLE_ID_CACHE: set[str] = set()

def _parse_env_list(env_var_name: str) -> set[str]:
    """
    Parses a comma or space separated environment variable into a set of strings.
    Used for reading protection lists from the environment.
    """
    if not (val := os.getenv(env_var_name, "")):
        return set()
    
    # Split by comma or any whitespace
    return {p.strip() for p in re.split(r'[,\s]+', val) if p.strip()}

def _is_id_protected(resource_id: str, protected_set: set[str]) -> bool:
    """
    Checks if a specific ID is in the protected set (handling 'all').
    """
    if not resource_id:
        return False
    
    if "all" in {s.lower() for s in protected_set}:
        return True
    
    return resource_id in protected_set

def _is_type_protected(resource_type: str, protected_set: set[str]) -> bool:
    """
    Checks if a resource type is in the protected set (handling 'all').
    """
    if not resource_type:
        return False
    
    lower_set = {s.lower() for s in protected_set}
    return "all" in lower_set or resource_type.lower() in lower_set

def check_user_protection(user_data: dict, action_desc: str):
    """
    Checks if a user is protected against modification or deletion.
    
    Checks against:
    - HOMEBOX_USERNAME (Primary Account)
    - HOMEBOX_PROTECTED_USERS (Modification + Deletion)
    - HOMEBOX_NON_DELETABLE_USERS (Deletion only)
    """
    u_id = user_data.get("id")
    u_email = user_data.get("email")
    u_username = user_data.get("username")
    
    # 1. Primary Account Protection (Mandatory for Deletion and Modification)
    env_username = os.getenv("HOMEBOX_USERNAME")
    is_primary = False
    if env_username:
        if u_email == env_username or u_username == env_username:
            is_primary = True
            
    if is_primary:
        # Blocks everything except Read
        restricted_actions = ["delete_user", "wipe_inventory", "change_password", "update_user", "change_email"]
        if action_desc in restricted_actions:
            raise ValueError(f"Action '{action_desc}' is disabled for the primary account ({env_username}).")

    # 2. HOMEBOX_PROTECTED_USERS (Blocks update, delete, etc.)
    _enforce_user_env_check(user_data, "HOMEBOX_PROTECTED_USERS", action_desc)

    # 3. HOMEBOX_NON_DELETABLE_USERS (Blocks delete and email changes)
    deletion_related = ["delete_user", "wipe_inventory", "change_email"]
    if action_desc in deletion_related:
        _enforce_user_env_check(user_data, "HOMEBOX_NON_DELETABLE_USERS", action_desc)

def _enforce_user_env_check(user_data: dict, env_var: str, action_desc: str):
    """
    Internal helper to check specific user protection environment variables.
    Handles caching of matched IDs.
    """
    is_non_deletable = "NON_DELETABLE" in env_var
    cache = _NON_DELETABLE_ID_CACHE if is_non_deletable else _PROTECTED_ID_CACHE
    
    u_id = user_data.get("id")
    u_email = user_data.get("email")

    if u_id and u_id in cache:
        raise ValueError(f"Action '{action_desc}' is disabled for protected user ID '{u_id}'.")

    if not (protected_set := _parse_env_list(env_var)):
        return

    # Check for 'all' keyword
    if "all" in {s.lower() for s in protected_set}:
        if u_id:
            cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for ALL users via {env_var}.")

    # Check by ID
    if u_id and u_id in protected_set:
        cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for user ID '{u_id}' via {env_var}.")

    # Check by Email
    if u_email and u_email in protected_set:
        if u_id:
            cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for user '{u_email}' via {env_var}.")

def protect_resource(resource_type: str, action: str):
    """
    Decorator to enforce guardrails on MCP tools.
    Prevents unauthorized Create, Update, or Delete operations based on environment configuration.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Inspect arguments to find 'id' if present
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            resource_id = bound_args.arguments.get("id")
            
            # 1. Type-Based Checks (e.g., READONLY for all 'locations')
            readonly_list = _parse_env_list("HOMEBOX_READONLY_RESOURCES")
            if _is_type_protected(resource_type, readonly_list):
                 raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_READONLY_RESOURCES.")
            
            # Check non-deletable types
            if action == "delete":
                non_del_list = _parse_env_list("HOMEBOX_NON_DELETABLE_RESOURCES")
                if _is_type_protected(resource_type, non_del_list):
                     raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_NON_DELETABLE_RESOURCES.")

            # 2. ID-Based Checks (Instance protection)
            if resource_id:
                # Protected IDs block Update + Delete
                if action in ["update", "delete"]:
                    protected_ids = _parse_env_list("HOMEBOX_PROTECTED_IDS")
                    if _is_id_protected(resource_id, protected_ids):
                        raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_PROTECTED_IDS.")
                
                # Non-deletable IDs block only Delete
                if action == "delete":
                    non_del_ids = _parse_env_list("HOMEBOX_NON_DELETABLE_IDS")
                    if _is_id_protected(resource_id, non_del_ids):
                         raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_NON_DELETABLE_IDS.")

            return await func(*args, **kwargs)
        return wrapper
    return decorator