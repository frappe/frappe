"""Daemon-wide defaults, overridable by environment."""

from __future__ import annotations

import os

FLOW_HOME = os.path.expanduser("~/.flow")
DEFAULT_DATA_DIR = os.path.join(FLOW_HOME, "server")
DEFAULT_CREDENTIALS_PATH = os.path.join(DEFAULT_DATA_DIR, "credentials.json")
EXTENSIONS_PATH = os.path.join(FLOW_HOME, "extensions")
DATA_DIR = os.path.expanduser(os.environ.get("FLOW_DATA_DIR", DEFAULT_DATA_DIR))
HOST = os.environ.get("FLOW_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLOW_PORT", "8787"))
# httpx still needs an authority in the URL when the transport is a unix socket;
# the name never resolves — it only labels the connection.
UDS_URL = "http://flow-daemon"
# Optional bearer for the daemon HTTP boundary. Required by the CLI when binding a
# non-loopback host; when set, every endpoint except healthz requires it.
AUTH_TOKEN = os.environ.get("FLOW_AUTH_TOKEN") or None
# When set, every event is also published to Redis channel `harness:<session_id>` so an
# external relay (e.g. Flow's bridge -> socketio) can stream to browsers. The channel
# prefix is a wire contract shared with the Flow bridge, so it stays `harness:`.
REDIS_URL = os.environ.get("FLOW_REDIS_URL") or None
# Filesystem fence for a session's `cwd`: an os.pathsep-separated list of roots a session
# may operate under. Empty (the default) = unrestricted (single-user dev). Enforced in
# SessionStore.create so every session-creation path (HTTP, embedded, Flow) is fenced.
# Entries are `~`-expanded and realpath-resolved by `path_policy.normalize_roots`.
ALLOWED_ROOTS = [p for p in os.environ.get("FLOW_ALLOWED_ROOTS", "").split(os.pathsep) if p]
# Browser origins allowed to call the API directly (comma-separated). Empty (the
# default) sends no CORS headers: browser clients must be same-origin or proxied.
CORS_ORIGINS = [o.strip() for o in os.environ.get("FLOW_CORS_ORIGINS", "").split(",") if o.strip()]
# API-key and OAuth credentials live beside the durable session directory. Deployments
# can still use FLOW_CREDENTIALS_PATH to place them elsewhere.
CREDENTIALS_PATH = os.path.expanduser(
	os.environ.get(
		"FLOW_CREDENTIALS_PATH",
		DEFAULT_CREDENTIALS_PATH,
	)
)
