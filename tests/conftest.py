import os
import random
import string

import pytest
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from homebox_mcp.server import mcp

load_dotenv(override=True)


def random_string(length=8):
    """Generate a random string of fixed length."""
    return "".join(random.choices(string.ascii_lowercase, k=length))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def fastmcp_client():
    """Fixture to provide an in-memory FastMCP Client for unit testing."""
    async with Client(mcp) as client:
        yield client


@pytest.fixture
async def server_session():
    """Fixture to start the Homebox MCP server and provide a session."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"

    if not env.get("HOMEBOX_API_KEY") and not env.get("HOMEBOX_USERNAME"):
        pytest.skip("No Homebox credentials found in environment")

    transport = StdioTransport(command=".venv/bin/python", args=["-m", "homebox_mcp.server"], env=env)
    async with Client(transport=transport) as client:
        yield client


async def run_scenario_session(env_vars):
    """Helper to run a one-off session with custom env vars."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["MCP_TRANSPORT"] = "stdio"
    # Enable safety switches for test setup/cleanup
    env["HOMEBOX_ALLOW_USER_REGISTRATION"] = "true"
    env["HOMEBOX_ALLOW_USER_DELETION"] = "true"
    env.update(env_vars)

    transport = StdioTransport(
        command=".venv/bin/python",
        args=["-m", "homebox_mcp.server"],
        env=env,
    )
    async with Client(transport=transport) as client:
        yield client


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
