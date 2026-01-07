import pytest
import sys
import os
from unittest.mock import patch
from homebox_mcp.server import main

def test_server_startup_stdio():
    """Verify main() defaults to stdio."""
    with (patch.object(sys, 'argv', ["homebox-mcp"]),
          patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}),
          patch("homebox_mcp.server.mcp") as mock_mcp,
          patch("uvicorn.run") as mock_uvicorn):
        
        main()
        mock_mcp.run.assert_called_once_with(transport="stdio")
        mock_uvicorn.run.assert_not_called()

def test_server_startup_sse_arg():
    """Verify main() switches to SSE when argument provided."""
    with (patch.object(sys, 'argv', ["homebox-mcp", "sse"]), 
          patch("homebox_mcp.server.mcp") as mock_mcp, 
          patch("uvicorn.run") as mock_uvicorn):
        
        main()
        mock_mcp.run.assert_not_called()
        mock_uvicorn.assert_called_once()

def test_server_startup_explicit_stdio_arg():
    """Verify main() respects explicit stdio argument."""
    with (patch.object(sys, 'argv', ["homebox-mcp", "stdio"]), 
          patch("homebox_mcp.server.mcp") as mock_mcp, 
          patch("uvicorn.run") as mock_uvicorn):
        
        main()
        mock_mcp.run.assert_called_once_with(transport="stdio")
        mock_uvicorn.run.assert_not_called()
