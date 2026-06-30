"""Consolidated LLM adapter for Studio AI.

This is the ONLY place that knows about provider-specific quirks. The agent
loop and tools talk to LLMs exclusively through the functions defined here.
"""

import json
import logging

import frappe
import litellm

from studio.ai.models import ModelRegistry

litellm.drop_params = True

logger = frappe.logger("studio.ai.llm")
logger.setLevel(logging.INFO)


# Transient failures worth retrying a streaming round: rate limits, 5xx, and
# connection/stream drops (incl. mid-stream resets). Matched by class name across the
# exception's MRO so subclasses — and both litellm and raw httpx transport errors — are
# covered without version-pinning exact types. Permanent errors (auth, bad request,
# content policy, not found) are deliberately absent: retrying them only burns tokens.
TRANSIENT_ERROR_NAMES = frozenset(
	{
		"RateLimitError",
		"Timeout",
		"TimeoutError",
		"APITimeoutError",
		"APIConnectionError",
		"InternalServerError",
		"ServiceUnavailableError",
		"RemoteProtocolError",
		"ReadError",
		"ReadTimeout",
		"ConnectError",
		"ConnectionError",
		"ChunkedEncodingError",
		"ProtocolError",
	}
)


def is_retryable(exc: BaseException) -> bool:
	"""True if this exception looks like a transient network/provider hiccup worth
	retrying. Walks the class MRO and matches by name (see TRANSIENT_ERROR_NAMES)."""
	return any(cls.__name__ in TRANSIENT_ERROR_NAMES for cls in type(exc).__mro__)


def loads_tolerant(raw: str) -> tuple[object | None, bool]:
	"""Parse tool-call argument JSON, tolerating the malformed JSON weaker models emit
	(single-quote delimiters, unescaped quotes, trailing commas, truncated/missing
	brackets). Strict json.loads first; on failure fall back to json_repair if available.
	Returns (parsed_or_None, was_repaired)."""
	raw = (raw or "").strip()
	if not raw:
		return None, False
	try:
		return json.loads(raw), False
	except json.JSONDecodeError:
		pass
	try:
		from json_repair import repair_json

		obj = repair_json(raw, return_objects=True)
		if obj not in ("", None, [], {}):
			return obj, True
	except Exception:
		pass
	return None, False


# Token/temperature budgets per task tier.
TASK_PARAMS = {
	"simple": {"max_tokens": 1000, "temperature": 0.5},
	"complex": {"max_tokens": 40000, "temperature": 0.7},
	"clarify": {"max_tokens": 700, "temperature": 0.1},
	"agent": {"max_tokens": 16000, "temperature": 0.3},
}


def patch_messages_for_provider(model: str, messages: list[dict]) -> None:
	"""Anthropic via OpenRouter reads cache_control from INSIDE a content block, not
	from the message level (a message-level marker is silently ignored → full input
	price every turn). For any Claude message that carries a cache_control marker with
	plain string content, wrap it in a text block and move the marker inside. Mutates
	in place. Callers set the markers (system prompt + page context); each becomes a
	cache breakpoint, well within Anthropic's limit of four."""
	if "claude-" in model:
		for m in messages:
			if isinstance(m.get("content"), str) and "cache_control" in m:
				m["content"] = [
					{"type": "text", "text": m["content"], "cache_control": m.pop("cache_control")}
				]


def complete(model: str, messages: list, params: dict, *, stream: bool, api_key: str | None = None):
	"""Plain completion. Returns the response iterator when streaming, else the
	text content. litellm handles fallback + retry."""
	patch_messages_for_provider(model, messages)
	logger.info(
		f"LLM | model={model} stream={stream} fallbacks={ModelRegistry.get_fallbacks(model)} params={params}\n"
		+ "\n".join(f"[{m['role']}] {m['content']!s}" for m in messages)
	)
	resp = litellm.completion(
		model=model,
		messages=messages,
		stream=stream,
		api_key=api_key or get_api_key(),
		# Fallbacks are disabled during streaming: litellm's mid-stream fallback
		# attempts __next__ on async generators returned by OpenRouter, causing
		# MidStreamFallbackError. Fallbacks only work safely for non-streaming calls.
		fallbacks=[] if stream else ModelRegistry.get_fallbacks(model),
		num_retries=1,
		# Emit a final usage chunk while streaming so the loop can tally tokens per
		# turn (dropped automatically for providers that don't support it).
		**({"stream_options": {"include_usage": True}} if stream else {}),
		**params,
	)
	if not stream:
		content = resp.choices[0].message.content or ""
		logger.info(f"LLM response | length={len(content)}\n{content}")
		return content
	return resp


def complete_with_tools(
	model: str,
	messages: list,
	tools: list,
	params: dict,
	*,
	api_key: str | None = None,
	stream: bool = False,
):
	"""Tool-calling completion. Returns the raw response (iterator when
	streaming). litellm handles fallback + retry."""
	patch_messages_for_provider(model, messages)
	logger.info(
		f"LLM tools | model={model} stream={stream} tools={[t['function']['name'] for t in tools]}\n"
		+ "\n".join(f"[{m['role']}] {m['content']}" for m in messages)
	)
	return litellm.completion(
		model=model,
		messages=messages,
		tools=tools,
		stream=stream,
		api_key=api_key or get_api_key(),
		# Fallbacks disabled during streaming — see comment in complete().
		fallbacks=[] if stream else ModelRegistry.get_fallbacks(model),
		num_retries=1,
		# Final usage chunk while streaming — see complete().
		**({"stream_options": {"include_usage": True}} if stream else {}),
		**params,
	)


def get_api_key() -> str | None:
	"""OpenRouter key, read from Studio Settings."""
	settings = frappe.get_single("Studio Settings")
	return settings.get_password("ai_api_key", raise_exception=False)
