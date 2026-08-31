"""Daemon-wide defaults, read from the environment once at import.

The full variable table lives in docs/development.md.
"""

from __future__ import annotations

import os

FLOW_HOME = os.path.expanduser("~/.flow")
DEFAULT_DATA_DIR = os.path.join(FLOW_HOME, "server")
DEFAULT_CREDENTIALS_PATH = os.path.join(DEFAULT_DATA_DIR, "credentials.json")
EXTENSIONS_PATH = os.path.join(FLOW_HOME, "extensions")

DATA_DIR = os.path.expanduser(os.environ.get("FLOW_DATA_DIR", DEFAULT_DATA_DIR))
HOST = os.environ.get("FLOW_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLOW_PORT", "8787"))

# dummy authority for httpx over a unix socket; the name never resolves
UDS_URL = "http://flow-daemon"

# bearer for the daemon API; required by the CLI on non-loopback TCP binds
AUTH_TOKEN = os.environ.get("FLOW_AUTH_TOKEN") or None

# also publish events to Redis channel `harness:<sid>` (prefix is the Flow bridge wire contract)
REDIS_URL = os.environ.get("FLOW_REDIS_URL") or None

# path fence for session cwds and path-taking tools; empty = unrestricted (never sandboxes bash)
ALLOWED_ROOTS = [p for p in os.environ.get("FLOW_ALLOWED_ROOTS", "").split(os.pathsep) if p]

# browser origins allowed to call the API; empty sends no CORS headers
CORS_ORIGINS = [o.strip() for o in os.environ.get("FLOW_CORS_ORIGINS", "").split(",") if o.strip()]

CREDENTIALS_PATH = os.path.expanduser(os.environ.get("FLOW_CREDENTIALS_PATH", DEFAULT_CREDENTIALS_PATH))
