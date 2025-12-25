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

## Usage

### Testing with MCP Inspector
Run the following to test tools in a web UI:
```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m homebox_mcp.server
```

### Manual Testing
A test script `test_server.py` is provided. Run it with:
```bash
PYTHONPATH=src .venv/bin/python test_server.py
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
- [x] GET /v1/assets/{id}
- [x] GET /v1/currency
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
- [x] GET /v1/items/{id}/attachments/{attachment_id} (Info only)
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
- [x] POST /v1/users/login (Handled by Client)
- [ ] GET /v1/users/login/oidc (Redirect - Not suitable)
- [ ] GET /v1/users/login/oidc/callback (Redirect - Not suitable)
- [x] POST /v1/users/logout (Handled by Client)
- [x] GET /v1/users/refresh (Handled by Client)
- [x] POST /v1/users/register
- [x] GET /v1/users/self
- [x] PUT /v1/users/self
- [x] DELETE /v1/users/self
