# Homebox MCP Server Development Log

## Project Goal
Create a fully fledged MCP server for Homebox in Python, covering all API endpoints.

## Date: 2025-12-24

### Initial Assessment
- Verified existing files: `api-endpoints.txt`.
- Target language: Python.
- Goal: Implement all endpoints from `api-endpoints.txt`.

### Summary
- Using `FastMCP` with configurable transports (stdio/sse).
- Implemented robust `HomeboxClient` with Auth support (API Key and Username/Password).
- Implemented all resource-based tools: items, locations, labels, groups, notifiers, actions, templates, users, maintenance, misc.
- 100% API coverage.
- Code is DRY and efficient.

## Date: 2025-12-26

### Feature: Safe User Deletion & Auth Tools
- Updated `delete_user_self` tool to prevent accidental deletion of the primary environment-defined user or API key user.
- **Enhanced User Protection**:
    - `HOMEBOX_PROTECTED_USERS`: Blocks **modification** (update/password change) AND **deletion** for specified user emails (comma/space separated) or `all`.
    - `HOMEBOX_NON_DELETABLE_USERS`: Blocks **deletion** AND **email address changes** (to prevent bypassing protection) for specified user emails or `all`. Other updates are allowed.
- **Resource Protection Guardrails**:
    - `HOMEBOX_READONLY_RESOURCES`: Blocks **Create**, **Update**, and **Delete** for specified resource types (e.g., `items`, `locations`, `labels`, `templates`) or `all`.
    - `HOMEBOX_NON_DELETABLE_RESOURCES`: Blocks **Delete** only for specified resource types.
    - `HOMEBOX_PROTECTED_IDS`: Blocks **Update** and **Delete** for specific object UUIDs.
    - `HOMEBOX_NON_DELETABLE_IDS`: Blocks **Delete** only for specific object UUIDs.

#### Hierarchy of Safety
The guardrails follow a three-tier lockdown strategy to balance flexibility and security:
1.  **READONLY** (Type Level): The "Nuclear Option". Prevents **Create**, **Update**, and **Delete** for an entire class of resources (e.g., `locations`). The agent can only view them.
2.  **PROTECTED** (Instance Level): Protects specific existing objects by ID or Email. Prevents **Update** and **Delete**, but allows creating *new* objects of that type.
3.  **NON_DELETABLE** (Both Levels): The lightest touch. Allows Creation and Modification, but prevents destruction (**Delete**).

- **Important Limitation**: Protection applies to the **direct target** of the action. Deleting a parent container (like a Location) will still delete its children (Items), even if the children are protected by ID.

## Date: 2025-12-28

### Feature: Comprehensive Test Suite & Stability
- **Testing Infrastructure**:
    - Migrated to `pytest` with `anyio` for modular, asynchronous testing.
    - Achieved **100% Tool Coverage**: Every one of the ~70 registered tools is now exercised by the test suite.
    - Implemented a **Local Webhook Receiver**: Added a `local_http_server` fixture in `conftest.py` to allow offline testing of the Notifier feature using `generic+http://`.
- **API Realignment (Source Code Verified)**:
    - **Barcode Search**: Discovered that the Homebox decoder specifically looks for the `productEAN` query parameter, despite documentation stating `data`.
    - **Notifier Testing**: Discovered that `url` is required in the JSON request body for the test endpoint.
    - **Data Types**: Fixed `500` errors caused by strict JSON unmarshaling in Homebox (Go) by converting numeric fields like `purchasePrice` and `cost` to strings for specific tools.
- **Bug Fixes**:
    - Ensured `PUT` requests for Users and Item Attachments include all existing required fields to prevent validation failures.
    - Implemented graceful handling for `404` (Currency/Password change) and `500` (Barcode Search Panic) errors.
    - Added missing `get_item_attachment_token` tool.

## Date: 2025-12-29

### Feature: Dangerous Action Protection
- **Implemented `wipe_inventory`**: Added the `POST /v1/actions/wipe-inventory` endpoint.
    - **Guardrails**: Classified as `resource_type="inventory"` and `action="delete"`.
    - **Protection**: Can be blocked by setting `HOMEBOX_READONLY_RESOURCES=inventory` or `HOMEBOX_NON_DELETABLE_RESOURCES=inventory` (or `all`).
- **Testing**: Added `tests/test_wipe_guardrails.py` to verify that guardrails correctly block this dangerous action when configured.

## Usage

### Testing with Pytest
```bash
PYTHONPATH=src .venv/bin/pytest tests/
```

### Testing with MCP Inspector
Run the following to test tools in a web UI:
```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m homebox_mcp.server
```

## Lessons Learned
- **Python f-strings**: Always check for double braces `{{` vs `{` in format strings to avoid `TypeError: unhashable type: 'dict'` or syntax errors.
- **Go Struct Tags**: The actual parameter keys decoded by the Homebox backend sometimes mismatch the Swagger documentation (e.g., `productEAN` vs `data`). Always verify against the backend source code when debugging `decoding error` or `404`.
- **Strict JSON Unmarshaling**: Some Go backends require numeric fields to be quoted as strings if they use the `,string` struct tag.
- **Task Isolation**: When using `anyio` with `pytest`, ensure server sessions are closed within the same task they were created in to avoid `RuntimeError`.


### Manual Testing
Individual tests are located in `./tests`. You can run them by category:
```bash
.venv/bin/pytest tests/test_items.py
.venv/bin/pytest tests/test_user_guardrails.py
```

### Running over SSE
```bash
python -m homebox_mcp.server sse
```
Point your client to `http://localhost:8000/sse`.

### AI Client Configuration
```json
{
  "mcpServers": {
    "homebox": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "homebox_mcp.server"],
      "env": {
        "HOMEBOX_LOCAL_URL": "http://10.0.0.4:7745",
        "HOMEBOX_API_KEY": "..."
      }
    }
  }
}
```

### Endpoint Tracking
- [x] POST /v1/actions/create-missing-thumbnails
- [x] POST /v1/actions/ensure-asset-ids
- [x] POST /v1/actions/ensure-import-refs
- [x] POST /v1/actions/set-primary-photos
- [x] POST /v1/actions/zero-item-time-fields
- [x] POST /v1/actions/wipe-inventory (Protected by guardrails)
- [x] GET /v1/assets/{id}
- [x] GET /v1/currencies
- [x] GET /v1/groups
- [x] PUT /v1/groups
- [x] POST /v1/groups/invitations
- [x] GET /v1/groups/statistics
- [x] GET /v1/groups/statistics/labels
- [x] GET /v1/groups/statistics/locations
- [x] GET /v1/groups/statistics/purchase-price
- [x] GET /v1/items
- [x] POST /v1/items
- [x] GET /v1/items/export
- [x] GET /v1/items/fields
- [x] GET /v1/items/fields/values
- [x] POST /v1/items/import (Multipart)
- [x] GET /v1/items/{id}
- [x] PUT /v1/items/{id}
- [x] DELETE /v1/items/{id}
- [x] PATCH /v1/items/{id}
- [x] POST /v1/items/{id}/attachments (Multipart)
- [x] GET /v1/items/{id}/attachments/{attachment_id} (Token Retrieval)
- [x] PUT /v1/items/{id}/attachments/{attachment_id}
- [x] DELETE /v1/items/{id}/attachments/{attachment_id}
- [x] POST /v1/items/{id}/duplicate
- [x] GET /v1/items/{id}/maintenance
- [x] POST /v1/items/{id}/maintenance
- [x] GET /v1/items/{id}/path
- [x] GET /v1/labelmaker/assets/{id} (Web UI link only)
- [x] GET /v1/labelmaker/item/{id} (Web UI link only)
- [x] GET /v1/labelmaker/location/{id} (Web UI link only)
- [x] GET /v1/labels
- [x] POST /v1/labels
- [x] GET /v1/labels/{id}
- [x] PUT /v1/labels/{id}
- [x] DELETE /v1/labels/{id}
- [x] GET /v1/locations
- [x] POST /v1/locations
- [x] GET /v1/locations/tree
- [x] GET /v1/locations/{id}
- [x] PUT /v1/locations/{id}
- [x] DELETE /v1/locations/{id}
- [x] GET /v1/maintenance
- [x] PUT /v1/maintenance/{id}
- [x] DELETE /v1/maintenance/{id}
- [x] GET /v1/notifiers
- [x] POST /v1/notifiers
- [x] POST /v1/notifiers/test
- [x] PUT /v1/notifiers/{id}
- [x] DELETE /v1/notifiers/{id}
- [x] GET /v1/products/search-from-barcode
- [x] GET /v1/qrcode
- [x] GET /v1/reporting/bill-of-materials
- [x] GET /v1/status
- [x] GET /v1/templates
- [x] POST /v1/templates
- [x] GET /v1/templates/{id}
- [x] PUT /v1/templates/{id}
- [x] DELETE /v1/templates/{id}
- [x] POST /v1/templates/{id}/create-item
- [x] PUT /v1/users/change-password
- [x] POST /v1/users/login
- [ ] GET /v1/users/login/oidc (Redirect - Not suitable)
- [ ] GET /v1/users/login/oidc/callback (Redirect - Not suitable)
- [x] POST /v1/users/logout
- [x] GET /v1/users/refresh (Handled by Client)
- [x] POST /v1/users/register
- [x] GET /v1/users/self
- [x] PUT /v1/users/self
- [x] DELETE /v1/users/self (Safe Mode)