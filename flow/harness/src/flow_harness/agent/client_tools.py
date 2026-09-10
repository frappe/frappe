"""Dispatch tools and terminal notifications over a session's callback URL.

A client (e.g. Flow) registers tool schemas plus a `callback_url`; the loop sends the
call there instead of running a builtin. `mode="execute"` runs the tool client-side;
`mode="confirm"` only asks the client for the human-facing approval prompt.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from flow_harness.events import RunEnded, ToolCall
from flow_harness.session.config import SessionConfig

_TERMINAL_RETRY_DELAYS = (0, 1, 5)


async def call_client(config: SessionConfig, session_id: str, call: ToolCall, *, mode: str) -> dict:
	url = config.callback_url
	if not url:
		raise RuntimeError(f"no callback_url configured; cannot dispatch client tool {call.name!r}")
	payload = {
		"callback_type": "tool",
		"session_id": session_id,
		"tool": call.name,
		"args": call.args,
		"user_context": config.user_context,
		"mode": mode,
	}
	return await _post(config, url, payload)


async def notify_run_ended(config: SessionConfig, session_id: str, event: RunEnded) -> None:
	"""Best-effort delivery with short retries. The durable log remains the source of
	truth, so the client can safely recover or receive the same terminal twice."""
	url = config.callback_url
	if not url or not config.notify_run_ended:
		return
	payload = {
		"callback_type": "run_ended",
		"session_id": session_id,
		"terminal_seq": event.seq,
	}
	for attempt, delay in enumerate(_TERMINAL_RETRY_DELAYS, start=1):
		if delay:
			await asyncio.sleep(delay)
		try:
			await _post(config, url, payload)
			return
		except httpx.HTTPError as error:
			if attempt == len(_TERMINAL_RETRY_DELAYS):
				logging.getLogger("flow").warning(
					"terminal callback failed for session %s at seq %s: %s",
					session_id,
					event.seq,
					error,
				)


async def _post(config: SessionConfig, url: str, payload: dict) -> dict:
	headers = {"X-Harness-Token": config.callback_token} if config.callback_token else {}
	async with httpx.AsyncClient(timeout=config.callback_timeout) as client:
		response = await client.post(url, json=payload, headers=headers)
		response.raise_for_status()
		body = response.json()
		# a client may wrap its return in an envelope (Frappe uses {"message": ...})
		if isinstance(body, dict) and isinstance(body.get("message"), dict):
			return body["message"]
		return body if isinstance(body, dict) else {}
