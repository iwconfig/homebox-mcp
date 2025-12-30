import pytest
import os
from homebox_mcp.guardrails import protect_resource, check_user_protection

# --- Helper Tests ---

def test_check_user_protection_primary(monkeypatch):
    monkeypatch.setenv("HOMEBOX_USERNAME", "admin@ex.com")
    
    # Should fail for primary user
    with pytest.raises(ValueError, match="primary account"):
        check_user_protection({"email": "admin@ex.com"}, "delete_user")

    # Should pass for other user
    check_user_protection({"email": "other@ex.com"}, "delete_user")

def test_check_user_protection_protected_env(monkeypatch):
    monkeypatch.setenv("HOMEBOX_USERNAME", "")
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "safe@ex.com, other@ex.com")
    
    with pytest.raises(ValueError, match="disabled for user 'safe@ex.com'"):
        check_user_protection({"email": "safe@ex.com"}, "update_user")

def test_check_user_protection_non_deletable(monkeypatch):
    monkeypatch.setenv("HOMEBOX_PROTECTED_USERS", "")
    monkeypatch.setenv("HOMEBOX_NON_DELETABLE_USERS", "keep@ex.com")
    
    # Update allowed
    check_user_protection({"email": "keep@ex.com"}, "update_user")
    
    # Delete blocked
    with pytest.raises(ValueError, match="disabled for user 'keep@ex.com'"):
        check_user_protection({"email": "keep@ex.com"}, "delete_user")

# --- Decorator Tests ---

@pytest.mark.asyncio
async def test_protect_resource_readonly(monkeypatch):
    monkeypatch.setenv("HOMEBOX_READONLY_RESOURCES", "items")
    
    @protect_resource("items", "create")
    async def create_item(name):
        return "created"
        
    with pytest.raises(ValueError, match="disabled for resource type 'items'"):
        await create_item(name="fail")

@pytest.mark.asyncio
async def test_protect_resource_id_block(monkeypatch):
    monkeypatch.setenv("HOMEBOX_READONLY_RESOURCES", "")
    monkeypatch.setenv("HOMEBOX_PROTECTED_IDS", "123-abc")
    
    @protect_resource("items", "update")
    async def update_item(id, name):
        return "updated"
        
    # Blocked ID
    with pytest.raises(ValueError, match="disabled for ID '123-abc'"):
        await update_item(id="123-abc", name="fail")
        
    # Safe ID
    assert await update_item(id="456-def", name="ok") == "updated"
