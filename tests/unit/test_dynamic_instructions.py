import os
from unittest.mock import patch

from homebox_mcp.server import _get_dynamic_instructions


def test_dynamic_instructions_basic():
    """Verify basic instructions are present."""
    with patch.dict(os.environ, {}, clear=True):
        instr = _get_dynamic_instructions()
        assert "MCP server for Homebox" in instr
        assert "Read-Only mode" not in instr
        # Default safety switch is OFF, so wipe disabled warning should be present
        assert "wipe_inventory" in instr


def test_dynamic_instructions_readonly():
    """Verify readonly warning is added."""
    with patch.dict(os.environ, {"HOMEBOX_READONLY_RESOURCES": "all"}):
        instr = _get_dynamic_instructions()
        assert "READ-ONLY mode" in instr


def test_dynamic_instructions_safety_switches():
    """Verify safety switch warnings."""
    # 1. Default (False)
    with patch.dict(os.environ, {}, clear=True):
        instr = _get_dynamic_instructions()
        assert "wipe_inventory' action is hard-disabled" in instr

    # 2. Enabled
    with patch.dict(os.environ, {"HOMEBOX_ALLOW_WIPE_INVENTORY": "true"}):
        instr = _get_dynamic_instructions()
        # Should NOT contain the disabled warning
        assert "wipe_inventory' action is hard-disabled" not in instr
