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

### Feature: Tiered Safety Switches & Refined Hierarchy
- **Tier 1: Safety Switches (Feature Flags)**:
    - Added mandatory environment variables to enable destructive tools. All default to `false`.
    - `HOMEBOX_ALLOW_WIPE_INVENTORY`: Enables `wipe_inventory`.
    - `HOMEBOX_ALLOW_USER_DELETION`: Enables `delete_user_self`.
    - `HOMEBOX_ALLOW_USER_REGISTRATION`: Enables `register_user`.
- **Tier 2: Universal Resource Guardrails**:
    - `HOMEBOX_READONLY_RESOURCES`: Blocks Create, Update, Delete for whole types.
    - `HOMEBOX_NON_DELETABLE_RESOURCES`: Blocks Delete for whole types.
- **Tier 3: Instance Protection**:
    - `HOMEBOX_PROTECTED_USERS`: Blocks modification and deletion of specific accounts.
    - **Refined Hierarchy**: Destructive actions like `wipe_inventory` now automatically check if the *authenticated user* is protected. The agent cannot wipe the inventory of a protected account even if the safety switch is on.
- **Code Consolidation**: Moved user protection logic into `guardrails.py` for cross-tool reuse.

## Date: 2025-12-30

### Feature: Test Suite Hardening
- **Refactored `test_generic_handlers_success`**: Replaced the loop-based smoke test with granular, parametrized tests for each tool group (items, locations, labels, etc.) to ensure specific parameters are correctly passed to the client.
- **Enhanced Data Validation Tests**:
    - **Zero-Dates**: `test_create_item_full_enrichment` now explicitly asserts that `purchaseTime`, `warrantyExpires`, etc., are set to `0001-01-01T00:00:00Z` to prevents backend issues.
    - **Bad Data**: Added tests for invalid inputs (`quantity="five"`) and file operations (empty/unreadable files).
    - **Partial Failures & Rollback**: Added `test_create_item_rollback` to verify that if item enrichment fails, the partially created item is automatically deleted.
    - **Edge Cases**: Added `test_upload_attachment_from_url_no_extension` to verify that file extensions are correctly appended when missing from the URL but the MIME type is known.
- **Integration Test Improvements**:
    - Added `test_item_import_success` using real CSV files.
    - Discovered that the Homebox CSV importer requires `HB.` prefixed headers (e.g., `HB.name`, `HB.location`) for successful matching.
- **Refinement**:
    - **Create Item**: Removed redundant `GET` request between `POST` and `PUT` steps, using the `POST` response directly to improve performance.
- **Robust Client Error Handling**:
    - Updated `HomeboxClient.request` to gracefully handle `json.JSONDecodeError`. If the server returns `Content-Type: application/json` but the body is HTML or a raw stack trace (common in 500 errors), the client now logs a warning and returns the text instead of crashing.
    - Added `test_request_json_decode_error` to verify this resilience.

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
- **Mocking Fidelity**: Generic smoke tests that loop over tools are insufficient for verifying parameter mapping. Explicit assertions for every tool call (checking `params` and `json` payloads) are necessary to catch regressions in argument handling.


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
- [x] POST /v1/users/register (Protected by safety switch)
- [x] GET /v1/users/self
- [x] PUT /v1/users/self
- [x] DELETE /v1/users/self (Safe Mode + Safety switch)

## Prompt Programming Strategy (Restored 2026-01-06)

To eliminate hallucination and ensure deterministic behavior, the agent now operates under a strict "Prompt Programming" contract. This treats prompts as executable code rather than conversational text.

### 1. The CO-STAR Framework
We refactored the `analyze-item` prompt into six logical blocks:
*   **C**ontext: Defines the agent's role (Inventory Assistant).
*   **O**bjective: Specific goal (Process Inbox -> Identify -> Enriched -> Move).
*   **S**tyle: Strict, deterministic, structured.
*   **T**one: Professional, no guessing.
*   **A**udience: The MCP Server (expecting JSON).
*   **R**ules (Strict): Explicit constraints (Identity Rule, Location Strategy).

### 2. Few-Shot Contrastive Examples ("Golden Examples")
We provide 3 concrete "Input -> Action" mappings to handle edge cases:
1.  **The Branded Product**: Shows how to extract Model/Serial numbers.
2.  **The Generic Item**: Shows how to use `None` for missing brands (preventing "Unknown" hallucinations) and how to infer location.
3.  **The Pre-Categorized Item**: Shows the "Location Preservation" rule (if an item is already sorted, keep its `locationId`).

### 3. Strict Type Enforcement (Prompts as APIs)
*   **Input**: `prompts.py` now accepts strict arguments.
*   **Output**: Tools like `finalize_processed_item` now use Python `Literal["homebox", "local"]` to restrict valid inputs.
*   **Return Values**: Tools return structured JSON objects (with `status`, `actions`, and `hint`) instead of plain strings, allowing the agent to self-correct if a step fails.
*   **Object Extraction Workflow**: `finalize_processed_item` now supports **Rotation** and **Extraction** in a single turn.
    *   `rotation`: Accepts any integer degree (e.g. `15`, `-42`) to fix image orientation. **Positive = Clockwise**.
    *   `extracted_objects`: Accepts a list of object definitions (metadata + crop boxes) to efficiently process mixed sets. 
        *   **Per-Object Rotation**: Each cutout can specify its own `rotation` degree applied AFTER cropping.
        *   **Centering**: PIL engine uses `BICUBIC` resampling and `expand=True` to keep rotated objects centered.
        *   **Automatic Coordinate Scaling**: Tools scale normalized coordinates (0-1000) to actual pixel resolution.
    *   **Token Optimization**: Agent-facing photos are scaled to `HOMEBOX_MAX_IMAGE_DIMENSION` (default 1024px) to preserve context window and reduce latency.
    *   The source item is automatically cleaned up upon success.

### 4. Logic Guardrails
*   **Visual Chain-of-Thought (VCoT)**: The agent MUST describe the scene, coordinates, and angles before acting.
*   **Leveling Rule**: Objects must be rotated to be perfectly vertical/horizontal.
*   **Terminology**: Use **"Object Cutouts"** or **"Extracted Objects"** instead of "children" to avoid confusion with database hierarchy.
*   **Identity Rule**: Never invent a brand for a generic object.
*   **Location Strategy**:
    *   *Inbox Items*: Move to best guess.
    *   *Existing Items*: Preserve current location.
    *   *Sub-Items*: Inherit parent location.
*   **Negative Signal**: Explicitly send `None` (null) for missing fields instead of "N/A".
*   **Mixed Sets**: Use `extracted_objects` to maintain a quantity of 1 for individual items.
