"""The web UI's settings, kept in `~/.flow/settings.json` beside the TUI's, so they
outlive the browser's storage and follow the user between browsers. The daemon never
reads them. Off with the `settings_api` policy switch, and in multi-tenant mode, where
the file would be shared by every site."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from flow_harness import settings
from flow_harness.server.policy import ServerPolicy, gate

# the web UI's own entry in the file
WEB_UI_KEY = "web_ui"


class SettingsPatch(BaseModel):
	model_config = ConfigDict(extra="forbid")

	settings: dict[str, Any]


def create_settings_router(*, policy: ServerPolicy | None = None) -> APIRouter:
	policy = policy or ServerPolicy()
	router = APIRouter(dependencies=gate(policy.settings_api))

	@router.get("/settings")
	async def read_settings():
		"""None until the web UI first saves, so it can seed them from the browser."""
		return {"settings": _web_ui()}

	@router.patch("/settings")
	async def update_settings(req: SettingsPatch):
		"""Merges the keys sent over the stored ones: a tab saves only what it changed,
		so it never undoes another tab's change to a different setting."""
		merged = {**(_web_ui() or {}), **req.settings}
		settings.save_setting(WEB_UI_KEY, merged)
		return {"settings": merged}

	return router


def _web_ui() -> dict | None:
	value = settings.load_settings().get(WEB_UI_KEY)
	return value if isinstance(value, dict) else None
