"""Dispatch tools and terminal notifications over a session's callback URL.

A client (e.g. Flow) registers tool schemas plus a `callback_url`; the loop sends the
call there instead of running a builtin. `mode="execute"` runs the tool client-side;
`mode="confirm"` only asks the client for the human-facing approval prompt. An execute
callback may answer `{"pending": true, "timeout": N}` and post the result within N
seconds to `POST /sessions/{sid}/tool_result` with the call's `result_token`.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable

import httpx

from flow_harness.events import ToolCall
from flow_harness.session.config import SessionConfig

_TERMINAL_RETRY_DELAYS = (1, 5, 15, 30, 60)  # seconds between tries; the last one repeats
_WAITING: dict[str, tuple[str, asyncio.Future[dict]]] = {}  # token -> (session id, result)


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
	if mode == "confirm":  # only fetches the approval prompt
		return await _post(config, url, payload)
	# registered before the callback, so a quick job can't post too early
	token = secrets.token_urlsafe(16)
	result = asyncio.get_running_loop().create_future()
	_WAITING[token] = (session_id, result)
	try:
		response = await _post(config, url, {**payload, "result_token": token})
		if not response.get("pending"):
			return response
		try:
			return await asyncio.wait_for(result, response.get("timeout"))
		except TimeoutError:
			raise RuntimeError(f"background tool {call.name!r} sent no result in time") from None
	finally:
		del _WAITING[token]


def deliver_result(session_id: str, token: str, result: dict) -> bool:
	"""Hand a background tool's result to the call waiting on `token`; False if none is."""
	if not is_waiting(session_id, token):
		return False
	_WAITING[token][1].set_result(result)
	return True


def is_waiting(session_id: str, token: str) -> bool:
	"""Whether a call still waits on `token`; false once it got a result, stopped or gave up."""
	waiting = _WAITING.get(token)
	return waiting is not None and waiting[0] == session_id and not waiting[1].done()


async def notify_run_ended(
	config: SessionConfig, session_id: str, terminal_seq: int, *, still_needed: Callable[[], bool]
) -> bool:
	"""Report a run's end until the client confirms it or `still_needed()` turns false; repeats are safe."""
	url = config.callback_url
	if not url or not config.notify_run_ended:
		return False
	payload = {
		"callback_type": "run_ended",
		"session_id": session_id,
		"terminal_seq": terminal_seq,
	}
	attempt = 0
	while still_needed():
		try:
			await _post(config, url, payload)
			return True
		except httpx.HTTPError as error:
			if attempt == len(_TERMINAL_RETRY_DELAYS) - 1:  # the quick retries are spent
				logging.getLogger("flow").warning(
					"terminal callback for session %s at seq %s keeps failing, retrying every %s s: %s",
					session_id,
					terminal_seq,
					_TERMINAL_RETRY_DELAYS[-1],
					error,
				)
		await asyncio.sleep(_TERMINAL_RETRY_DELAYS[min(attempt, len(_TERMINAL_RETRY_DELAYS) - 1)])
		attempt += 1
	return False


async def _post(config: SessionConfig, url: str, payload: dict) -> dict:
	headers = httpx.Headers(config.callback_headers)
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
