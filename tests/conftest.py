import os

import pytest
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(override=True)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def server_session():
    """Fixture to start the Homebox MCP server and provide a session."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"

    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        pytest.skip("No Homebox credentials found in environment")

    server_params = StdioServerParameters(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=env)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.fixture(scope="session")
def local_http_server():
    """Starts a simple HTTP server in a background thread to act as a webhook receiver."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        def log_message(self, format, *args):
            return  # Silence server logs

    server = HTTPServer(("127.0.0.1", 0), WebhookHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
