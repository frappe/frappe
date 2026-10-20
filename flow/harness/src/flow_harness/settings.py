"""User-level preferences at ~/.flow/settings.json.

Distinct from `flow_harness.config` (daemon defaults from the environment): these are
conveniences the client persists across sessions, e.g. the last model the user
picked in the TUI, or the web UI's settings (`server/routes/settings`). Reads are
tolerant — a missing or corrupt file means "no preferences" — so a bad write can
never block startup.
"""

from __future__ import annotations

import json
import os
from tempfile import mkstemp

from flow_harness import config

SETTINGS_PATH = os.path.join(config.FLOW_HOME, "settings.json")


def load_settings() -> dict:
	try:
		with open(SETTINGS_PATH, encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}


def save_setting(key: str, value) -> None:
	settings = load_settings()
	settings[key] = value
	directory = os.path.dirname(SETTINGS_PATH)
	os.makedirs(directory, exist_ok=True)
	fd, tmp = mkstemp(prefix=".settings.", dir=directory)
	try:
		os.chmod(tmp, 0o600)
		with os.fdopen(fd, "w", encoding="utf-8") as f:
			json.dump(settings, f, indent=2)
		os.replace(tmp, SETTINGS_PATH)
	finally:
		if os.path.exists(tmp):
			os.unlink(tmp)


def last_model() -> str | None:
	value = load_settings().get("last_model")
	return value if isinstance(value, str) and value else None


def resolve_startup_model() -> str:
	"""Explicit FLOW_MODEL beats the remembered model; the catalog fallback is last.

	The remembered value is the raw name the user last picked — it is not
	validated against the live catalog, which can change between runs.
	"""
	return os.environ.get("FLOW_MODEL") or last_model() or "mock"
