"""Dispatch to a client's own tools over its callback URL.

A client (e.g. Flow) registers tool schemas plus a `callback_url`; the loop sends the
call there instead of running a builtin. `mode="execute"` runs the tool client-side;
`mode="confirm"` only asks the client for the human-facing approval prompt.
"""

from __future__ import annotations

import httpx

from flow_harness.events import ToolCall
from flow_harness.session.config import SessionConfig


async def call_client(config: SessionConfig, session_id: str, call: ToolCall, *, mode: str) -> dict:
	url = config.callback_url
	if not url:
		raise RuntimeError(f"no callback_url configured; cannot dispatch client tool {call.name!r}")
	payload = {
		"session_id": session_id,
		"tool": call.name,
		"args": call.args,
		"user_context": config.user_context,
		"mode": mode,
	}
	headers = {}
	if config.callback_token:
		headers["X-Harness-Token"] = config.callback_token
	async with httpx.AsyncClient(timeout=config.callback_timeout) as client:
		response = await client.post(url, json=payload, headers=headers)
		response.raise_for_status()
		body = response.json()
		# a client may wrap its return in an envelope (Frappe uses {"message": ...})
		if isinstance(body, dict) and isinstance(body.get("message"), dict):
			return body["message"]
		return body if isinstance(body, dict) else {}
