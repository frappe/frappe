import logging

import frappe
import litellm
from frappe import _

from studio.ai.block_codec import BlockCodec
from studio.ai.models import ModelRegistry
from studio.ai.prompts import MODIFY_SYSTEM_PROMPT, SYSTEM_PROMPT
from studio.ai.session import AISession
from studio.utils import has_page_write_perm

litellm.drop_params = True
logger = frappe.logger("studio.ai")
logger.setLevel(logging.INFO)

TASK_PARAMS = {
	"simple": {"max_tokens": 1000, "temperature": 0.5},
	"complex": {"max_tokens": 40000, "temperature": 0.7},
}


def call_llm(messages: list, model: str, task_tier: str, api_key: str, stream: bool = False):
	params = TASK_PARAMS[task_tier]
	return litellm.completion(model=model, messages=messages, api_key=api_key, stream=stream, **params)


def _emit(event_suffix: str, page_id: str, user: str, prefix: str = "ai_generation", **kwargs):
	frappe.publish_realtime(
		f"{prefix}_{event_suffix}_{page_id}",
		{"page_id": page_id, **kwargs},
		user=user,
	)


def _progress_stage(content: str) -> str | None:
	"""Extract a human-readable stage from the tail of a partial JSON stream."""
	lookback = content[-400:].replace(" ", "")
	for section_type in ("section", "nav", "header", "footer"):
		if f'"label":"{section_type}' in lookback or f'"name":"{section_type}' in lookback:
			return f"Building {section_type}…"
	return None


def run_generation_job(prompt: str, model: str, page_id: str, user: str):
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("ai_api_key", raise_exception=False)

	session = AISession.get_or_create(page_id, model)
	context = session.build_context_string()
	session.add_message("user", prompt, task_type="generate")

	_emit("progress", page_id, user, message=f"Generating with {ModelRegistry.get_label(model)}…")

	system = SYSTEM_PROMPT + (f"\n\n{context}" if context else "")
	content = ""
	try:
		llm_messages = [
			{"role": "system", "content": system},
			{"role": "user", "content": f"Create a page for: {prompt}"},
		]
		for chunk in call_llm(llm_messages, model, "complex", api_key, stream=True):
			delta = chunk.choices[0].delta.content
			if not delta:
				continue
			content += delta
			_emit("stream", page_id, user, chunk=delta)
			stage = _progress_stage(content)
			if stage:
				_emit("progress", page_id, user, message=stage)

		logger.info(f"run_generation_job stream done | model={model} length={len(content)}")
		block = BlockCodec.parse_blocks(content)
		session.add_message("assistant", "Page generated successfully.", task_type="generate")
		_emit("complete", page_id, user, block=block)

	except Exception as e:
		logger.error(f"run_generation_job failed: {e}\n\n{content}", exc_info=True)
		logger.info(f"Raw LLM Output for Generate: \n{content}\n")
		frappe.log_error(title="Studio AI: generation error", message=str(e))
		_emit("error", page_id, user, message=str(e))


@frappe.whitelist()
@has_page_write_perm()
def generate_page_from_prompt(prompt: str, model: str | None, page_id: str) -> dict:
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw(_("You do not have permission to modify pages"))

	settings = frappe.get_single("Studio Settings")
	if not settings.get_password("ai_api_key", raise_exception=False):
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	resolved_model = model or ModelRegistry.get_default()

	frappe.enqueue(
		run_generation_job,
		queue="long",
		prompt=prompt,
		model=resolved_model,
		page_id=page_id,
		user=frappe.session.user,
	)

	frappe.local.response.http_status_code = 202
	return {"status": "accepted"}


@frappe.whitelist()
@has_page_write_perm()
def get_ai_session(page_id: str, model: str | None = None) -> dict:
	session = AISession.get_or_create(page_id, model)
	return {
		"messages": session.get_messages(),
		"selected_model": session._doc.selected_model or "",
	}


@frappe.whitelist()
@has_page_write_perm()
def clear_ai_session(page_id: str) -> dict:
	session = AISession.get_or_create(page_id)
	session.clear()
	return {"status": "ok"}


def run_modify_job(prompt: str, block_context: str, model: str, page_id: str, user: str, component_id: str):
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("ai_api_key", raise_exception=False)

	session = AISession.get_or_create(page_id, model)
	context = session.build_context_string()
	session.add_message("user", prompt, task_type="modify", component_id=component_id)

	_emit("progress", page_id, user, prefix="ai_modify", message="Updating block…")

	compressed = BlockCodec.strip_context(block_context)
	system = MODIFY_SYSTEM_PROMPT + (f"\n\nConversation history:\n{context}" if context else "")

	content = ""
	try:
		llm_messages = [
			{"role": "system", "content": system},
			{"role": "user", "content": f"Current block:\n{compressed}\n\nRequest: {prompt}"},
		]
		for chunk in call_llm(llm_messages, model, "complex", api_key, stream=True):
			delta = chunk.choices[0].delta.content
			if not delta:
				continue
			content += delta
			_emit("stream", page_id, user, prefix="ai_modify", chunk=delta, component_id=component_id)

		logger.info(f"run_modify_job stream done | model={model} length={len(content)}")
		block = BlockCodec.parse_blocks(content)
		session.add_message("assistant", "Block updated.", task_type="modify", component_id=component_id)
		_emit("complete", page_id, user, prefix="ai_modify", block=block, component_id=component_id)

	except Exception as e:
		logger.error(f"run_modify_job failed: {e}", exc_info=True)
		logger.info(f"Raw LLM Output for Modify: \n{content}\n")
		frappe.log_error(title="Studio AI: modify error", message=str(e))
		_emit("error", page_id, user, prefix="ai_modify", message=str(e))


@frappe.whitelist()
@has_page_write_perm()
def modify_block_from_prompt(
	prompt: str, block_context: str, model: str | None, page_id: str, component_id: str
) -> dict:
	settings = frappe.get_single("Studio Settings")
	if not settings.get_password("ai_api_key", raise_exception=False):
		frappe.throw(_("OpenRouter API key is not configured. Please set it in Studio Settings."))

	resolved_model = model or ModelRegistry.get_default()

	frappe.enqueue(
		run_modify_job,
		queue="long",
		prompt=prompt,
		block_context=block_context,
		model=resolved_model,
		page_id=page_id,
		user=frappe.session.user,
		component_id=component_id,
	)

	frappe.local.response.http_status_code = 202
	return {"status": "accepted"}
