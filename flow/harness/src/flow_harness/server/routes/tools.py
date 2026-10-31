"""Which tools a session may enable under this daemon's policy — built-ins and
loaded extension tools, the lists a client offers when composing a session's
`tools` and `extension_tools`. Off with the `tools_api` policy switch; extension
rows also stay hidden while the `extensions` switch is off, like the extension
info routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Request

from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.session.store import SessionStore
from flow_harness.tools import BUILTIN_TOOLS, BUNDLED_TOOLS, Tool


def create_tools_router(
	resolve_store: Callable[[Request], SessionStore], *, policy: ServerPolicy | None = None
) -> APIRouter:
	policy = policy or ServerPolicy()
	router = APIRouter(dependencies=gate(policy.tools_api))

	@router.get("/tools")
	async def list_tools(request: Request):
		store = resolve_store(request)
		allowed = store.tool_allowlist
		runtime = store.extension_runtime
		extension_tools = runtime.tools if policy.extensions else {}
		# a built-in stays listed even when an extension overrides its name
		rows = [_row(tool) for tool in BUILTIN_TOOLS.values()]
		rows += [_row(tool, bundled=True) for tool in BUNDLED_TOOLS.values()]
		rows += [_row(tool, extension=runtime.tool_sources[name]) for name, tool in extension_tools.items()]
		return {"tools": [row for row in rows if allowed is None or row["name"] in allowed]}

	return router


def _row(tool: Tool, *, extension: str | None = None, bundled: bool = False) -> dict:
	return {
		"name": tool.name,
		"description": tool.prompt_snippet or tool.description,
		"extension": extension,
		"bundled": bundled,
	}
