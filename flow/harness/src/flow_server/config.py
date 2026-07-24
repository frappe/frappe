"""Daemon-wide defaults, overridable by environment."""

from __future__ import annotations

import os

DATA_DIR = os.environ.get("FLOW_SERVER_DATA_DIR", os.path.join(os.getcwd(), ".flow-server-data"))
DEFAULT_MODEL = os.environ.get("FLOW_SERVER_MODEL", "mock")
HOST = os.environ.get("FLOW_SERVER_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLOW_SERVER_PORT", "8787"))
# Optional bearer for the daemon HTTP boundary. Required by the CLI when binding a
# non-loopback host; when set, every endpoint except healthz requires it.
AUTH_TOKEN = os.environ.get("FLOW_SERVER_AUTH_TOKEN") or None
# When set, every event is also published to Redis channel `harness:<session_id>` so an
# external relay (e.g. Flow's bridge -> socketio) can stream to browsers. The channel
# prefix is a wire contract shared with the Flow bridge, so it stays `harness:`.
REDIS_URL = os.environ.get("FLOW_SERVER_REDIS_URL") or None
# Filesystem fence for a session's `cwd`: an os.pathsep-separated list of roots a session
# may operate under. Empty (the default) = unrestricted (single-user dev). Enforced in
# SessionStore.create so every session-creation path (HTTP, embedded, Flow) is fenced.
ALLOWED_ROOTS = [p for p in os.environ.get("FLOW_SERVER_ALLOWED_ROOTS", "").split(os.pathsep) if p]
# OAuth/subscription tokens (e.g. Codex). User-global, not per-project, so it lives in the
# home dir rather than under DATA_DIR (which defaults to cwd). Written 0600.
CREDENTIALS_PATH = os.environ.get(
	"FLOW_SERVER_CREDENTIALS_PATH", os.path.expanduser("~/.flow-server/credentials.json")
)
