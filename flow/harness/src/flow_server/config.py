"""Daemon-wide defaults, overridable by environment."""

from __future__ import annotations

import os

DATA_DIR = os.environ.get("FLOW_SERVER_DATA_DIR", os.path.join(os.getcwd(), ".flow-server-data"))
DEFAULT_MODEL = os.environ.get("FLOW_SERVER_MODEL", "mock")
HOST = os.environ.get("FLOW_SERVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLOW_SERVER_PORT", "8787"))
# When set, every event is also published to Redis channel `harness:<session_id>` so an
# external relay (e.g. Flow's bridge -> socketio) can stream to browsers. The channel
# prefix is a wire contract shared with the Flow bridge, so it stays `harness:`.
REDIS_URL = os.environ.get("FLOW_SERVER_REDIS_URL") or None
