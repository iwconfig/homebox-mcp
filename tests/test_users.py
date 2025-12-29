import pytest
import uuid
import random
import string

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

@pytest.mark.anyio
async def test_user_lifecycle(server_session):
    # 1. Get Self
    res = await server_session.call_tool("get_user_self", {})
    assert not getattr(res, "isError", False)

    # 2. Register User
    new_name = "Test User"
    new_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    new_pass = "Password123!"
    
    res = await server_session.call_tool("register_user", {
        "name": new_name,
        "email": new_email,
        "password": new_pass
    })
    assert not getattr(res, "isError", False)

    # 3. Login
    res = await server_session.call_tool("login_user", {
        "username": new_email,
        "password": new_pass
    })
    assert not getattr(res, "isError", False)
    assert "Logged in" in res.content[0].text

    # 4. Update Self (while logged in as new user)
    updated_name = "Updated Test User"
    res = await server_session.call_tool("update_user_self", {"name": updated_name})
    assert not getattr(res, "isError", False)
    assert updated_name in res.content[0].text

    # 5. Change Password
    res = await server_session.call_tool("change_password", {
        "current": new_pass,
        "new": "NewPassword123!"
    })
    assert not getattr(res, "isError", False)

    # 6. Delete User Self
    res = await server_session.call_tool("delete_user_self", {})
    assert not getattr(res, "isError", False)

    # 7. Logout (reverts to default user)
    res = await server_session.call_tool("logout_user", {})
    assert not getattr(res, "isError", False)
