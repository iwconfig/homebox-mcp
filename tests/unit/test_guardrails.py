import pytest
import os
from homebox_mcp.guardrails import (
    protect_resource, 
    check_user_protection, 
    _parse_env_list,
    _PROTECTED_ID_CACHE,
    _NON_DELETABLE_ID_CACHE
)

@pytest.fixture(autouse=True)
def clear_caches():
    """Ensure internal ID caches are clean between tests."""
    _PROTECTED_ID_CACHE.clear()
    _NON_DELETABLE_ID_CACHE.clear()

# --- Parsing Logic ---

def test_parse_env_list():
    assert _parse_env_list("VAR_NAME") == set()
    
    os.environ["TEST_VAR"] = "a, b c   d"
    assert _parse_env_list("TEST_VAR") == {"a", "b", "c", "d"}
    
    os.environ["TEST_VAR"] = "all"
    assert _parse_env_list("TEST_VAR") == {"all"}

# --- User Protection Logic ---

def test_check_user_protection_primary(monkeypatch):
    monkeypatch.setenv("HOMEBOX_USERNAME", "admin")
    
    # Match by username
    with pytest.raises(ValueError, match="primary account"):
        check_user_protection({"username": "admin"}, "delete_user")
        
    # Match by email
    with pytest.raises(ValueError, match="primary account"):
        check_user_protection({"email": "admin"}, "update_user")

def test_check_user_protection_lists(monkeypatch):
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "prot@ex.com")
    monkeypatch.setenv("HOMEBOX_NON_DELETABLE_USERS", "keep@ex.com")
    
    # 1. Protected User - Block Update
    with pytest.raises(ValueError, match="is disabled for user 'prot@ex.com' via HOMEBOX_PROTECTED_USERS"):
        check_user_protection({"email": "prot@ex.com", "id": "u1"}, "update_user")
        
    # 2. Non-Deletable User - Allow Update
    check_user_protection({"email": "keep@ex.com", "id": "u2"}, "update_user")
    
    # 3. Non-Deletable User - Block Delete
    with pytest.raises(ValueError, match="is disabled for user 'keep@ex.com' via HOMEBOX_NON_DELETABLE_USERS"):
        check_user_protection({"email": "keep@ex.com", "id": "u2"}, "delete_user")

def test_user_protection_caching(monkeypatch):
    """Verify that once a user is matched by email, their ID is cached for protection."""
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "trap@ex.com")
    
    user_data = {"email": "trap@ex.com", "id": "uuid-999"}
    
    with pytest.raises(ValueError):
        check_user_protection(user_data, "update_user")
        
    assert "uuid-999" in _PROTECTED_ID_CACHE
    
    # Email changed, but ID remains in cache
    changed_user = {"email": "new@ex.com", "id": "uuid-999"}
    with pytest.raises(ValueError, match="disabled for protected user ID 'uuid-999'"):
        check_user_protection(changed_user, "update_user")

def test_user_protection_all_keyword(monkeypatch):
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "all")
    with pytest.raises(ValueError, match="disabled for ALL users"):
        check_user_protection({"email": "any@any.com"}, "delete_user")

# --- Decorator Logic ---

@pytest.mark.asyncio
async def test_protect_resource_types(monkeypatch):
    monkeypatch.setenv("HOMEBOX_READONLY_RESOURCES", "items")
    
    @protect_resource("items", "create")
    async def dummy(): return "ok"
    
    with pytest.raises(ValueError, match="HOMEBOX_READONLY_RESOURCES"):
        await dummy()

@pytest.mark.asyncio
async def test_protect_resource_id_merging(monkeypatch):
    monkeypatch.setenv("HOMEBOX_PROTECTED_IDS", "id-1, id-2")
    
    @protect_resource("items", "update")
    async def dummy(id): return "ok"
    
    with pytest.raises(ValueError, match="ID 'id-1'"):
        await dummy(id="id-1")
        
    assert await dummy(id="id-safe") == "ok"

@pytest.mark.asyncio
async def test_protect_resource_non_deletable_only(monkeypatch):
    monkeypatch.setenv("HOMEBOX_NON_DELETABLE_RESOURCES", "locations")
    
    @protect_resource("locations", "create")
    async def create(): return "ok"
    @protect_resource("locations", "delete")
    async def delete(id): return "ok"
    
    # Create is allowed
    assert await create() == "ok"
    # Delete is blocked
    with pytest.raises(ValueError, match="HOMEBOX_NON_DELETABLE_RESOURCES"):
        await delete(id="1")