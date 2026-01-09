import os
import re
import functools
import inspect
from typing import Set

# Cache to remember IDs that matched protected emails during this process lifecycle
_PROTECTED_ID_CACHE = set()
_NON_DELETABLE_ID_CACHE = set()

def _parse_env_list(env_var_name: str) -> set[str]:
    """Parses a comma or space separated environment variable into a set of strings."""
    if not (val := os.getenv(env_var_name, "")): return set()
    return {p.strip() for p in re.split(r'[,\s]+', val) if p.strip()}

def _is_id_protected(resource_id: str, protected_set: set[str]) -> bool:
    """Checks if a specific ID is in the protected set (handling 'all')."""
    if not resource_id: return False
    if "all" in {s.lower() for s in protected_set}: return True
    return resource_id in protected_set

def _is_type_protected(resource_type: str, protected_set: set[str]) -> bool:
    """Checks if a resource type is in the protected set (handling 'all')."""
    if not resource_type: return False
    lower_set = {s.lower() for s in protected_set}
    return "all" in lower_set or resource_type.lower() in lower_set

def check_user_protection(user_data: dict, action_desc: str):
    """Checks if a user is protected against modification or deletion."""
    u_id, u_email, u_username = user_data.get("id"), user_data.get("email"), user_data.get("username")
    env_username, is_primary = os.getenv("HOMEBOX_USERNAME"), False
    if env_username:
        if u_email == env_username or u_username == env_username: is_primary = True
    if is_primary and action_desc in ["delete_user", "wipe_inventory", "change_password", "update_user", "change_email"]:
        raise ValueError(f"Action '{action_desc}' is disabled for the primary account ({env_username}).")
    _enforce_user_env_check(user_data, "HOMEBOX_PROTECTED_USERS", action_desc)
    if action_desc in ["delete_user", "wipe_inventory", "change_email"]:
        _enforce_user_env_check(user_data, "HOMEBOX_NON_DELETABLE_USERS", action_desc)

def _enforce_user_env_check(user_data: dict, env_var: str, action_desc: str):
    """Internal helper to check specific user protection env vars."""
    cache = _NON_DELETABLE_ID_CACHE if "NON_DELETABLE" in env_var else _PROTECTED_ID_CACHE
    u_id, u_email = user_data.get("id"), user_data.get("email")
    if u_id and u_id in cache: raise ValueError(f"Action '{action_desc}' is disabled for protected user ID '{u_id}'.")
    if not (protected_set := _parse_env_list(env_var)): return
    if "all" in {s.lower() for s in protected_set}:
        if u_id: cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for ALL users via {env_var}.")
    if u_id and u_id in protected_set:
        cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for user ID '{u_id}' via {env_var}.")
    if u_email and u_email in protected_set:
        if u_id: cache.add(u_id)
        raise ValueError(f"Action '{action_desc}' is disabled for user '{u_email}' via {env_var}.")

def protect_resource(resource_type: str, action: str):
    """Decorator to enforce guardrails on MCP tools."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            sig = inspect.signature(func); bound_args = sig.bind(*args, **kwargs); bound_args.apply_defaults()
            resource_id = bound_args.arguments.get("id")
            if _is_type_protected(resource_type, _parse_env_list("HOMEBOX_READONLY_RESOURCES")):
                 raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_READONLY_RESOURCES.")
            if action == "delete" and _is_type_protected(resource_type, _parse_env_list("HOMEBOX_NON_DELETABLE_RESOURCES")):
                 raise ValueError(f"Action '{action}' is disabled for resource type '{resource_type}' via HOMEBOX_NON_DELETABLE_RESOURCES.")
            if resource_id:
                if action in ["update", "delete"] and _is_id_protected(resource_id, _parse_env_list("HOMEBOX_PROTECTED_IDS")):
                    raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_PROTECTED_IDS.")
                if action == "delete" and _is_id_protected(resource_id, _parse_env_list("HOMEBOX_NON_DELETABLE_IDS")):
                     raise ValueError(f"Action '{action}' is disabled for ID '{resource_id}' via HOMEBOX_NON_DELETABLE_IDS.")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
