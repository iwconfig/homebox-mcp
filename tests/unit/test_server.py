import pytest
import sys
import os
from unittest.mock import patch
from homebox_mcp.server import main

def test_server_startup_stdio(monkeypatch):
    """Verify main() defaults to stdio."""
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    with (patch.object(sys, 'argv', ["homebox-mcp"]), 
          patch("homebox_mcp.server.mcp") as mock_mcp):
        
        main()
        mock_mcp.run.assert_called_once_with(transport="stdio")

def test_server_startup_sse_arg(monkeypatch):
    """Verify main() switches to SSE when argument provided."""
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    with (patch.object(sys, 'argv', ["homebox-mcp", "sse"]), 
          patch("homebox_mcp.server.mcp") as mock_mcp):
        
        main()
        mock_mcp.run.assert_called_once_with(transport="sse", host="0.0.0.0", port=8000)

def test_server_startup_explicit_stdio_arg(monkeypatch):
    """Verify main() respects explicit stdio argument."""
    monkeypatch.setenv("MCP_TRANSPORT", "sse") # Should be overridden by CLI
    with (patch.object(sys, 'argv', ["homebox-mcp", "stdio"]), 
          patch("homebox_mcp.server.mcp") as mock_mcp):
        
        main()
        mock_mcp.run.assert_called_once_with(transport="stdio")
