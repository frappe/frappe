"""Whitelisted endpoints for the Studio AI agent.

A single conversational entry point — `run` — drives the unified agent loop for
one user turn (generation and editing alike). `cancel` requests that a running turn
abort at its next stream chunk; `get_ai_session`/`clear_ai_session` read and reset the
per-page chat history.
"""

import json
import logging

import frappe
from frappe import _

from studio.ai import llm
from studio.ai.agent.loop import run_agent_job
from studio.ai.models import ModelRegistry
from studio.ai.session import AISession
from studio.utils import has_page_write_perm

logger = frappe.logger("studio.ai.api")
logger.setLevel(logging.INFO)


@frappe.whitelist()
@has_page_write_perm()
def run(
	prompt: str,
	page_context: str,
	page_id: str,
	model: str | None = None,
	selected_block_ids: list | str | None = None,
):
	"""Single entry point: run the agent for one user turn."""
	logger.info(f"run: page_id={page_id}, model={model}")

	try:
		json.loads(page_context)
	except (json.JSONDecodeError, TypeError):
		frappe.throw(_("Invalid page context JSON"))

	resolved_model = model or ModelRegistry.get_default()
	api_key = llm.get_api_key()
	if not api_key:
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	session = AISession.get_or_create(page_id, resolved_model)
	if AISession.is_session_running(session.name):
		frappe.local.response.http_status_code = 429
		return {"status": "busy", "message": _("Another AI request is still processing. Please wait.")}

	session.append_message("user", prompt, message_type="chat", task_type="agent")

	# Background queue (not now=True): a streaming turn can run for tens of seconds, and
	# now=True would hold this web worker open for the whole stream — exhausting the worker
	# pool under concurrency. Realtime events flow over Redis pub/sub regardless of process.
	frappe.enqueue(
		run_agent_job,
		queue="long",
		timeout=600,
		prompt=prompt,
		page_context_json=page_context,
		model=resolved_model,
		api_key=api_key,
		user=frappe.session.user,
		page_id=page_id,
		session_id=session.name,
		selected_block_ids=_parse_block_ids(selected_block_ids),
	)
	frappe.local.response.http_status_code = 202
	return {"status": "accepted", "session_id": session.name}


@frappe.whitelist()
@has_page_write_perm()
def cancel(session_id: str):
	"""Request that the currently-running turn for this session abort at its next stream
	chunk. The loop closes the LLM stream — Anthropic / OpenRouter stop billing for further
	tokens once the connection drops."""
	if session_id:
		frappe.cache.set_value(f"studio_ai_cancel:{session_id}", "1", expires_in_sec=300)
	return {"status": "ok"}


@frappe.whitelist()
@has_page_write_perm()
def get_ai_session(page_id: str, model: str | None = None) -> dict:
	session = AISession.get_or_create(page_id, model)
	return {"messages": session.get_messages(), "selected_model": session.selected_model or ""}


@frappe.whitelist()
@has_page_write_perm()
def clear_ai_session(page_id: str) -> dict:
	session = AISession.get_or_create(page_id)
	session.clear()
	return {"status": "ok"}


def _parse_block_ids(selected_block_ids: list | str | None) -> list[str]:
	if isinstance(selected_block_ids, str):
		try:
			selected_block_ids = json.loads(selected_block_ids)
		except (json.JSONDecodeError, TypeError):
			return []
	return selected_block_ids if isinstance(selected_block_ids, list) else []
